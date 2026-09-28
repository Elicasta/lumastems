import { useEffect, useMemo, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';

type RuntimeStatus = {
  ready: boolean;
  appData: string;
  pythonPath?: string | null;
  enginePath?: string | null;
  detail: string;
};

type StemResult = {
  stem: string;
  path: string;
  model: string;
  stage: string;
};

type SeparationResult = {
  outputDir: string;
  manifest: string;
  stems: StemResult[];
};

type PresetId = 'auto6' | 'auto7' | 'band' | 'worship7';

const PRESETS: Array<{
  id: PresetId;
  name: string;
  detail: string;
  stems: string;
}> = [
  {
    id: 'auto6',
    name: 'Auto Quality 6',
    detail: 'Recommended. Curated vocal ensemble + higher-quality rhythm + band detail passes.',
    stems: 'Vocals · Drums · Bass · Guitar · Piano · Other'
  },
  {
    id: 'auto7',
    name: 'Auto Worship 7',
    detail: 'Auto Quality 6 plus lead vocal and BGV / choir separation.',
    stems: 'Lead Vocal · BGV / Choir · Drums · Bass · Guitar · Piano · Other'
  },
  {
    id: 'band',
    name: 'Stable Band 6',
    detail: 'Single-model fallback using the proven six-stem path.',
    stems: 'Vocals · Drums · Bass · Guitar · Piano · Other'
  },
  {
    id: 'worship7',
    name: 'Stable Worship 7',
    detail: 'Stable Band 6 plus the backing-vocal specialist.',
    stems: 'Lead Vocal · BGV / Choir · Drums · Bass · Guitar · Piano · Other'
  }
];

function basename(path: string) {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

function App() {
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [source, setSource] = useState('');
  const [output, setOutput] = useState('');
  const [preset, setPreset] = useState<PresetId>('auto6');
  const [busy, setBusy] = useState<'setup' | 'separate' | null>(null);
  const [message, setMessage] = useState('Ready to set up LumaStems.');
  const [error, setError] = useState('');
  const [result, setResult] = useState<SeparationResult | null>(null);

  const selectedPreset = useMemo(
    () => PRESETS.find((item) => item.id === preset) ?? PRESETS[0],
    [preset]
  );

  async function refreshRuntime() {
    try {
      const status = await invoke<RuntimeStatus>('runtime_status');
      setRuntime(status);
      if (status.ready) setMessage('Engine ready.');
    } catch (err) {
      setError(String(err));
    }
  }

  useEffect(() => {
    void refreshRuntime();
  }, []);

  async function chooseSource() {
    const selected = await open({
      multiple: false,
      directory: false,
      filters: [
        {
          name: 'Audio',
          extensions: ['wav', 'mp3', 'flac', 'm4a', 'aiff', 'aif', 'ogg']
        }
      ]
    });

    if (typeof selected === 'string') {
      setSource(selected);
      setResult(null);
      setError('');
    }
  }

  async function chooseOutput() {
    const selected = await open({
      multiple: false,
      directory: true
    });

    if (typeof selected === 'string') {
      setOutput(selected);
      setError('');
    }
  }

  async function prepareEngine() {
    setBusy('setup');
    setError('');
    setMessage('Installing the local AI engine. This only happens once.');

    try {
      const status = await invoke<RuntimeStatus>('ensure_runtime');
      setRuntime(status);
      setMessage(status.ready ? 'Engine ready.' : status.detail);
    } catch (err) {
      setError(String(err));
      setMessage('Engine setup failed.');
    } finally {
      setBusy(null);
    }
  }

  async function separate() {
    if (!source) {
      setError('Choose a song first.');
      return;
    }

    if (!output) {
      setError('Choose an output folder.');
      return;
    }

    if (!runtime?.ready) {
      setError('Prepare the engine first.');
      return;
    }

    setBusy('separate');
    setError('');
    setResult(null);
    setMessage(
      preset === 'auto7'
        ? 'Running automatic quality separation, then Lead + BGV.'
        : preset === 'auto6'
          ? 'Running automatic multi-model quality separation.'
          : preset === 'worship7'
            ? 'Separating Stable Band 6, then Lead + BGV.'
            : 'Separating Stable Band 6.'
    );

    try {
      const separated = await invoke<SeparationResult>('separate_audio', {
        source,
        outputDir: output,
        preset
      });

      setResult(separated);
      setMessage('Separation complete.');
    } catch (err) {
      setError(String(err));
      setMessage('Separation failed.');
    } finally {
      setBusy(null);
    }
  }

  async function openInstallLog() {
    try {
      await invoke('open_install_log');
    } catch (err) {
      setError(String(err));
    }
  }

  async function revealResult() {
    if (!result?.outputDir) return;

    try {
      await invoke('open_output_folder', { path: result.outputDir });
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">LS</div>
          <div>
            <h1>LumaStems</h1>
            <p>Local stem separation</p>
          </div>
        </div>

        <div className={`engine-pill ${runtime?.ready ? 'ready' : ''}`}>
          <span className="status-dot" />
          {runtime?.ready ? 'Engine ready' : 'Engine not prepared'}
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow">SOURCE SEPARATION</p>
        <h2>Turn a stereo master into usable band stems.</h2>
        <p className="hero-copy">
          Auto Quality chooses the existing curated models for you. It first cleans the
          vocal/instrumental split, then uses stronger rhythm and band-detail passes automatically.
        </p>
      </section>

      <section className="workspace">
        <div className="panel source-panel">
          <div className="panel-heading">
            <div>
              <span className="step">01</span>
              <h3>Song</h3>
            </div>
            <button className="text-button" onClick={chooseSource}>Choose file</button>
          </div>

          <button className={`drop-zone ${source ? 'selected' : ''}`} onClick={chooseSource}>
            <span className="file-icon">♪</span>
            <span className="drop-title">{source ? basename(source) : 'Choose an audio file'}</span>
            <span className="drop-subtitle">
              {source ? source : 'WAV, MP3, FLAC, M4A, AIFF or OGG'}
            </span>
          </button>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <span className="step">02</span>
              <h3>Separation</h3>
            </div>
          </div>

          <div className="preset-grid">
            {PRESETS.map((item) => (
              <button
                key={item.id}
                className={`preset-card ${preset === item.id ? 'active' : ''}`}
                onClick={() => setPreset(item.id)}
              >
                <div className="preset-top">
                  <strong>{item.name}</strong>
                  {item.id === 'auto6' && <span className="recommended">RECOMMENDED</span>}
                  {item.id === 'auto7' && <span className="recommended">WORSHIP</span>}
                  {item.id === 'band' && <span className="recommended">FALLBACK</span>}
                </div>
                <span>{item.detail}</span>
                <small>{item.stems}</small>
              </button>
            ))}
          </div>

          <div className="selected-summary">
            <div>
              <span>Selected</span>
              <strong>{selectedPreset.name}</strong>
            </div>
            <p>{selectedPreset.stems}</p>
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <span className="step">03</span>
              <h3>Output</h3>
            </div>
            <button className="text-button" onClick={chooseOutput}>Choose folder</button>
          </div>

          <button className="folder-row" onClick={chooseOutput}>
            <span className="folder-icon">▱</span>
            <span>
              <strong>{output ? basename(output) : 'Choose output folder'}</strong>
              <small>{output || 'Each song gets its own LumaStems folder.'}</small>
            </span>
          </button>
        </div>
      </section>

      <section className="action-bar">
        <div className="status-copy">
          <span className={error ? 'error-indicator' : 'activity-indicator'} />
          <div>
            <strong>{error || message}</strong>
            <small>
              {preset.startsWith('auto')
                ? 'No manual tuning. LumaStems runs the curated ensemble and quality passes automatically.'
                : 'Stable fallback uses the proven single-model path.'}
            </small>
          </div>
        </div>

        {!runtime?.ready ? (
          <div className="action-buttons">
            {error && (
              <button className="secondary-button" onClick={openInstallLog}>
                Open Install Log
              </button>
            )}
            <button
              className="primary-button"
              disabled={busy !== null}
              onClick={prepareEngine}
            >
              {busy === 'setup' ? 'Preparing engine…' : 'Prepare Engine'}
            </button>
          </div>
        ) : (
          <button
            className="primary-button"
            disabled={busy !== null || !source || !output}
            onClick={separate}
          >
            {busy === 'separate' ? 'Separating…' : 'Separate Stems'}
          </button>
        )}
      </section>

      {result && (
        <section className="result-panel">
          <div className="result-heading">
            <div>
              <p className="eyebrow">COMPLETE</p>
              <h3>{basename(result.outputDir)}</h3>
            </div>
            <button className="secondary-button" onClick={revealResult}>
              Show in Finder
            </button>
          </div>

          <div className="stem-list">
            {result.stems.map((stem, index) => (
              <div className="stem-row" key={stem.stem}>
                <span className="stem-index">{String(index + 1).padStart(2, '0')}</span>
                <strong>{stem.stem.replaceAll('_', ' ')}</strong>
                <span>{basename(stem.path)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <footer>
        <span>LumaStems 0.3.0</span>
        <span>Local processing · Apple Silicon</span>
      </footer>
    </main>
  );
}

export default App;
