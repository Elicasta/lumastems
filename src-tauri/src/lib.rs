use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::{AppHandle, Manager};

const ENGINE_VERSION: &str = "0.2.0";

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeStatus {
    ready: bool,
    app_data: String,
    python_path: Option<String>,
    engine_path: Option<String>,
    detail: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
struct CliStem {
    stem: String,
    path: String,
    model: String,
    stage: String,
}

#[derive(Debug, Clone, Deserialize)]
struct CliResult {
    output_dir: String,
    manifest: String,
    stems: Vec<CliStem>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct SeparationResult {
    output_dir: String,
    manifest: String,
    stems: Vec<CliStem>,
}

fn app_data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_data_dir()
        .map_err(|error| format!("Could not resolve LumaStems app data directory: {error}"))
}

fn runtime_paths(app: &AppHandle) -> Result<(PathBuf, PathBuf, PathBuf, PathBuf), String> {
    let app_data = app_data_dir(app)?;
    let runtime = app_data.join("runtime");
    let python = runtime.join("bin/python");
    let engine = runtime.join("bin/lumastems");
    let stamp = app_data.join("engine-version");
    Ok((app_data, python, engine, stamp))
}

fn runtime_status_sync(app: &AppHandle) -> Result<RuntimeStatus, String> {
    let (app_data, python, engine, stamp) = runtime_paths(app)?;
    let installed_version = fs::read_to_string(&stamp).ok();
    let ready = python.exists()
        && engine.exists()
        && installed_version.as_deref().map(str::trim) == Some(ENGINE_VERSION);

    let detail = if ready {
        format!("Local engine {ENGINE_VERSION} is ready.")
    } else if engine.exists() {
        format!("LumaStems engine {ENGINE_VERSION} needs to be updated.")
    } else {
        "Local AI engine has not been prepared yet.".to_string()
    };

    Ok(RuntimeStatus {
        ready,
        app_data: app_data.display().to_string(),
        python_path: python.exists().then(|| python.display().to_string()),
        engine_path: engine.exists().then(|| engine.display().to_string()),
        detail,
    })
}

#[tauri::command]
fn runtime_status(app: AppHandle) -> Result<RuntimeStatus, String> {
    runtime_status_sync(&app)
}

fn run_checked(command: &mut Command, label: &str) -> Result<String, String> {
    let output = command
        .output()
        .map_err(|error| format!("{label} could not start: {error}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if !output.status.success() {
        let details = if !stderr.is_empty() {
            stderr
        } else if !stdout.is_empty() {
            stdout
        } else {
            format!("process exited with {}", output.status)
        };
        return Err(format!("{label} failed: {details}"));
    }

    Ok(stdout)
}

fn ensure_runtime_sync(app: &AppHandle) -> Result<RuntimeStatus, String> {
    let current = runtime_status_sync(app)?;
    if current.ready {
        return Ok(current);
    }

    let (app_data, python, _engine, stamp) = runtime_paths(app)?;
    let bin_dir = app_data.join("bin");
    let runtime_dir = app_data.join("runtime");
    let model_dir = app_data.join("models");

    fs::create_dir_all(&bin_dir)
        .map_err(|error| format!("Could not create runtime bin directory: {error}"))?;
    fs::create_dir_all(&model_dir)
        .map_err(|error| format!("Could not create model directory: {error}"))?;

    let uv = bin_dir.join("uv");
    if !uv.exists() {
        let mut install_uv = Command::new("/bin/sh");
        install_uv
            .arg("-c")
            .arg("curl -LsSf https://astral.sh/uv/install.sh | sh")
            .env("UV_INSTALL_DIR", &bin_dir)
            .env("UV_NO_MODIFY_PATH", "1");
        run_checked(&mut install_uv, "Installing the LumaStems runtime manager")?;
    }

    if !uv.exists() {
        return Err(format!(
            "Runtime manager installation completed but {} was not created.",
            uv.display()
        ));
    }

    let mut install_python = Command::new(&uv);
    install_python.args(["python", "install", "3.12"]);
    run_checked(&mut install_python, "Installing managed Python")?;

    if !python.exists() {
        let mut create_venv = Command::new(&uv);
        create_venv
            .arg("venv")
            .arg(&runtime_dir)
            .args(["--python", "3.12"]);
        run_checked(&mut create_venv, "Creating LumaStems runtime")?;
    }

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|error| format!("Could not locate bundled engine resources: {error}"))?;
    let wheel = resource_dir.join("engine/lumastems.whl");
    if !wheel.exists() {
        return Err(format!(
            "The bundled LumaStems engine is missing: {}",
            wheel.display()
        ));
    }

    let mut install_engine = Command::new(&uv);
    install_engine
        .arg("pip")
        .arg("install")
        .arg("--python")
        .arg(&python)
        .arg("--upgrade")
        .arg(&wheel);
    run_checked(&mut install_engine, "Installing LumaStems AI dependencies")?;

    fs::write(&stamp, format!("{ENGINE_VERSION}\n"))
        .map_err(|error| format!("Could not save engine version: {error}"))?;

    runtime_status_sync(app)
}

#[tauri::command]
async fn ensure_runtime(app: AppHandle) -> Result<RuntimeStatus, String> {
    tauri::async_runtime::spawn_blocking(move || ensure_runtime_sync(&app))
        .await
        .map_err(|error| format!("Engine setup task failed: {error}"))?
}

fn parse_cli_result(stdout: &str) -> Result<CliResult, String> {
    let payload = stdout
        .lines()
        .rev()
        .find_map(|line| line.strip_prefix("LUMASTEMS_RESULT="))
        .ok_or_else(|| {
            let tail = stdout.lines().rev().take(12).collect::<Vec<_>>();
            format!(
                "LumaStems completed without returning a result manifest. Output: {}",
                tail.into_iter().rev().collect::<Vec<_>>().join(" | ")
            )
        })?;

    serde_json::from_str(payload)
        .map_err(|error| format!("Could not parse LumaStems result: {error}"))
}

fn separate_audio_sync(
    app: &AppHandle,
    source: &str,
    output_dir: &str,
    preset: &str,
) -> Result<SeparationResult, String> {
    let allowed = ["quick", "band", "worship", "worship7"];
    if !allowed.contains(&preset) {
        return Err(format!("Unknown separation preset: {preset}"));
    }

    let source_path = Path::new(source);
    if !source_path.is_file() {
        return Err(format!("Audio file does not exist: {}", source_path.display()));
    }

    let output_path = Path::new(output_dir);
    fs::create_dir_all(output_path)
        .map_err(|error| format!("Could not create output folder: {error}"))?;

    let status = runtime_status_sync(app)?;
    if !status.ready {
        return Err("LumaStems engine is not prepared. Run Prepare Engine first.".to_string());
    }

    let (app_data, _python, engine, _stamp) = runtime_paths(app)?;
    let model_dir = app_data.join("models");

    let mut command = Command::new(&engine);
    command
        .arg("split")
        .arg(source_path)
        .args(["--preset", preset])
        .arg("--output")
        .arg(output_path)
        .args(["--format", "WAV", "--json"])
        .env("LUMASTEMS_MODEL_DIR", &model_dir)
        .env("AUDIO_SEPARATOR_MODEL_DIR", &model_dir);

    let stdout = run_checked(&mut command, "Stem separation")?;
    let result = parse_cli_result(&stdout)?;

    Ok(SeparationResult {
        output_dir: result.output_dir,
        manifest: result.manifest,
        stems: result.stems,
    })
}

#[tauri::command]
async fn separate_audio(
    app: AppHandle,
    source: String,
    output_dir: String,
    preset: String,
) -> Result<SeparationResult, String> {
    tauri::async_runtime::spawn_blocking(move || {
        separate_audio_sync(&app, &source, &output_dir, &preset)
    })
    .await
    .map_err(|error| format!("Separation task failed: {error}"))?
}

#[tauri::command]
fn open_output_folder(path: String) -> Result<(), String> {
    let target = Path::new(&path);
    if !target.exists() {
        return Err(format!("Output folder no longer exists: {}", target.display()));
    }

    let status = Command::new("/usr/bin/open")
        .arg(target)
        .status()
        .map_err(|error| format!("Could not open Finder: {error}"))?;

    if status.success() {
        Ok(())
    } else {
        Err(format!("Finder exited with {status}"))
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            runtime_status,
            ensure_runtime,
            separate_audio,
            open_output_folder
        ])
        .run(tauri::generate_context!())
        .expect("error while running LumaStems");
}
