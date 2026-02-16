import { useState, useRef, useEffect } from 'react';
import { Upload, FileSpreadsheet, Link2, AlertCircle, AlertTriangle, CheckCircle2, ChevronDown, X, HardDrive, Copy, Check } from 'lucide-react';

const getBase = () => {
  const origin = window.location.origin;
  const basePath = (import.meta.env.BASE_URL || '/');
  return origin + (basePath.endsWith('/') ? basePath.slice(0, -1) : basePath);
};

function CourierMultiSelect({ sheetName, allCouriers, selected, onSelect, assignedCouriers }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const toggle = (courier) => {
    if (selected.includes(courier)) {
      onSelect(sheetName, selected.filter(c => c !== courier));
    } else {
      onSelect(sheetName, [...selected, courier]);
    }
  };

  return (
    <div className="multi-select-dropdown" ref={ref}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          border: '1px solid var(--border)',
          borderRadius: 8,
          cursor: 'pointer',
          background: 'var(--card-bg)',
          minHeight: 40,
          flexWrap: 'wrap',
          gap: 4,
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, flex: 1 }}>
          {selected.length === 0 && <span className="text-muted text-sm">Select couriers...</span>}
          {selected.map(c => (
            <span key={c} className="tag">
              {c}
              <span className="remove-tag" onClick={(e) => { e.stopPropagation(); toggle(c); }}>x</span>
            </span>
          ))}
        </div>
        <ChevronDown size={16} style={{ color: 'var(--muted)', flexShrink: 0 }} />
      </div>
      {open && (
        <div className="dropdown-menu">
          {allCouriers.map(c => {
            const isSelected = selected.includes(c);
            const isAssigned = assignedCouriers.has(c) && !isSelected;
            return (
              <div
                key={c}
                className={`dropdown-item ${isSelected ? 'selected' : ''} ${isAssigned ? 'disabled' : ''}`}
                onClick={() => !isAssigned && toggle(c)}
                title={isAssigned ? `Already assigned to another sheet` : ''}
              >
                <input type="checkbox" checked={isSelected} readOnly style={{ pointerEvents: 'none' }} />
                <span>{c}</span>
                {isAssigned && <span className="text-xs text-muted" style={{ marginLeft: 'auto' }}>(assigned)</span>}
              </div>
            );
          })}
          {allCouriers.length === 0 && (
            <div className="dropdown-item disabled">No couriers configured. Add in Settings.</div>
          )}
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button
      className="btn btn-xs btn-outline"
      onClick={handleCopy}
      title="Copy to clipboard"
      style={{ marginLeft: 6, verticalAlign: 'middle' }}
    >
      {copied ? <Check size={14} style={{ color: 'var(--success)' }} /> : <Copy size={14} />}
    </button>
  );
}

export default function ProcessPricing({ token }) {
  const [step, setStep] = useState(1);
  const [merchantName, setMerchantName] = useState('');
  const [inputMode, setInputMode] = useState('upload'); // 'upload' or 'drive'
  const [file, setFile] = useState(null);
  const [driveLink, setDriveLink] = useState('');
  const [driveFileId, setDriveFileId] = useState('');
  const [driveFileName, setDriveFileName] = useState('');
  const [sheets, setSheets] = useState([]);
  const [mapping, setMapping] = useState({});
  const [allCouriers, setAllCouriers] = useState([]);
  const [detecting, setDetecting] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [validationErrors, setValidationErrors] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [result, setResult] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [accessDenied, setAccessDenied] = useState(null); // { message, serviceAccountEmail }
  const fileRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${getBase()}/api/couriers`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (r.ok) {
          const data = await r.json();
          setAllCouriers(data);
        }
      } catch {}
    })();
  }, [token]);

  const handleFileSelect = (f) => {
    if (!f) return;
    const ext = f.name.split('.').pop().toLowerCase();
    if (!['xlsx', 'xls'].includes(ext)) {
      setError('Please upload an Excel file (.xlsx or .xls).');
      return;
    }
    setFile(f);
    setError('');
    setResult(null);
    setValidationErrors([]);
    setAccessDenied(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    handleFileSelect(f);
  };

  const detectSheets = async () => {
    if (inputMode === 'upload') {
      if (!file || !merchantName.trim()) {
        setError('Please enter a merchant name and upload a file.');
        return;
      }
    } else {
      if (!driveLink.trim() || !merchantName.trim()) {
        setError('Please enter a merchant name and a Drive link.');
        return;
      }
    }

    setDetecting(true);
    setError('');
    setAccessDenied(null);

    try {
      let data;

      if (inputMode === 'upload') {
        const fd = new FormData();
        fd.append('file', file);
        const r = await fetch(`${getBase()}/api/detect-sheets`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({ detail: 'Error detecting sheets.' }));
          throw new Error(err.detail || 'Error detecting sheets.');
        }
        data = await r.json();
      } else {
        const r = await fetch(`${getBase()}/api/detect-sheets-from-drive`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ drive_link: driveLink.trim() }),
        });
        if (!r.ok) {
          const err = await r.json().catch(() => ({ detail: 'Error reading Drive file.' }));
          throw new Error(err.detail || 'Error reading Drive file.');
        }
        data = await r.json();

        if (data.status === 'access_denied') {
          setAccessDenied({
            message: data.message,
            serviceAccountEmail: data.service_account_email
          });
          return;
        }

        setDriveFileId(data.drive_file_id || '');
        setDriveFileName(data.file_name || '');
      }

      setSheets(data.sheets || []);
      const initMapping = {};
      for (const s of (data.sheets || [])) {
        if (s.valid) {
          initMapping[s.name] = [];
        }
      }
      setMapping(initMapping);
      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setDetecting(false);
    }
  };

  const handleCourierSelect = (sheetName, couriers) => {
    setMapping(prev => ({ ...prev, [sheetName]: couriers }));
  };

  const assignedCouriers = new Set();
  Object.values(mapping).forEach(couriers => {
    couriers.forEach(c => assignedCouriers.add(c));
  });

  const processFile = async (force = false) => {
    const hasAnyMapping = Object.values(mapping).some(v => v.length > 0);
    if (!hasAnyMapping) {
      setError('Please map at least one sheet to a courier.');
      return;
    }

    setProcessing(true);
    setError('');
    setValidationErrors([]);
    if (!force) setWarnings([]);
    setResult(null);

    try {
      const fd = new FormData();
      fd.append('merchant_name', merchantName.trim());
      fd.append('sheet_courier_mapping', JSON.stringify(mapping));
      if (force) fd.append('force', 'true');

      if (inputMode === 'upload') {
        fd.append('file', file);
      } else {
        fd.append('drive_link', driveLink.trim());
      }

      const r = await fetch(`${getBase()}/api/process`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });

      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: 'Processing failed.' }));
        if (r.status === 422 && err.detail?.errors) {
          setValidationErrors(err.detail.errors);
          setError(err.detail.message || 'Validation failed.');
        } else {
          setError(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
        }
        return;
      }

      const data = await r.json();

      if (data.status === 'warnings') {
        setWarnings(data.warnings || []);
        return;
      }

      setWarnings([]);
      setResult(data);
      setStep(3);
    } catch (e) {
      setError(e.message);
    } finally {
      setProcessing(false);
    }
  };

  const resetAll = () => {
    setStep(1);
    setMerchantName('');
    setFile(null);
    setDriveLink('');
    setDriveFileId('');
    setDriveFileName('');
    setSheets([]);
    setMapping({});
    setError('');
    setValidationErrors([]);
    setWarnings([]);
    setResult(null);
    setAccessDenied(null);
  };

  const canProceed = inputMode === 'upload'
    ? (file && merchantName.trim())
    : (driveLink.trim() && merchantName.trim());

  return (
    <div className="card">
      <h2 style={{ fontSize: '1.15rem', marginTop: 0, marginBottom: 20 }}>Process Courier Pricing</h2>

      {/* Stepper */}
      <div className="stepper">
        <div className={`step ${step >= 1 ? (step > 1 ? 'completed' : 'active') : ''}`}>
          <div className="step-circle">{step > 1 ? '\u2713' : '1'}</div>
          <span>Upload</span>
        </div>
        <div className={`step-line ${step > 1 ? 'completed' : ''}`} />
        <div className={`step ${step >= 2 ? (step > 2 ? 'completed' : 'active') : ''}`}>
          <div className="step-circle">{step > 2 ? '\u2713' : '2'}</div>
          <span>Map Couriers</span>
        </div>
        <div className={`step-line ${step > 2 ? 'completed' : ''}`} />
        <div className={`step ${step >= 3 ? 'active' : ''}`}>
          <div className="step-circle">{step >= 3 ? '\u2713' : '3'}</div>
          <span>Result</span>
        </div>
      </div>

      {/* Step 1: Upload */}
      {step === 1 && (
        <div className="flex flex-col gap-4">
          <div>
            <label>Merchant Name *</label>
            <input
              type="text"
              value={merchantName}
              onChange={(e) => setMerchantName(e.target.value)}
              placeholder="e.g. Acme Corp"
            />
          </div>

          {/* Input mode toggle */}
          <div>
            <label style={{ marginBottom: 8, display: 'block' }}>Input Source *</label>
            <div className="input-mode-toggle">
              <button
                className={`input-mode-btn ${inputMode === 'upload' ? 'active' : ''}`}
                onClick={() => { setInputMode('upload'); setAccessDenied(null); setError(''); }}
              >
                <Upload size={16} /> Upload File
              </button>
              <button
                className={`input-mode-btn ${inputMode === 'drive' ? 'active' : ''}`}
                onClick={() => { setInputMode('drive'); setAccessDenied(null); setError(''); }}
              >
                <HardDrive size={16} /> Google Drive Link
              </button>
            </div>
          </div>

          {inputMode === 'upload' && (
            <div>
              <div
                className={`dropzone ${dragOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".xlsx,.xls"
                  style={{ display: 'none' }}
                  onChange={(e) => handleFileSelect(e.target.files?.[0])}
                />
                {file ? (
                  <div className="flex items-center gap-3" style={{ justifyContent: 'center' }}>
                    <FileSpreadsheet size={22} style={{ color: 'var(--success)' }} />
                    <span style={{ fontWeight: 600 }}>{file.name}</span>
                    <button
                      className="btn btn-xs btn-outline"
                      onClick={(e) => { e.stopPropagation(); setFile(null); }}
                      style={{ marginLeft: 8 }}
                    >
                      <X size={14} /> Remove
                    </button>
                  </div>
                ) : (
                  <div>
                    <Upload size={28} style={{ color: 'var(--muted)', marginBottom: 8 }} />
                    <p style={{ margin: 0 }}>Drag & drop your Excel file here or click to browse</p>
                    <p className="text-xs text-muted" style={{ margin: '4px 0 0' }}>Accepts .xlsx, .xls</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {inputMode === 'drive' && (
            <div>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={driveLink}
                  onChange={(e) => { setDriveLink(e.target.value); setAccessDenied(null); }}
                  placeholder="Paste Google Drive file link here..."
                  style={{ paddingLeft: 36 }}
                />
                <Link2 size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
              </div>
              <p className="text-xs text-muted" style={{ marginTop: 4 }}>
                Supports links like: drive.google.com/file/d/... or docs.google.com/spreadsheets/d/...
              </p>
            </div>
          )}

          {/* Access denied card */}
          {accessDenied && (
            <div className="message-warning">
              <div className="flex items-center gap-2" style={{ marginBottom: 8 }}>
                <AlertTriangle size={16} />
                <strong>Cannot Access File</strong>
              </div>
              {accessDenied.message.split('\n').filter(Boolean).map((line, i) => (
                <p key={i} style={{ margin: '0 0 6px', fontSize: '0.88rem' }}>{line}</p>
              ))}
              {accessDenied.serviceAccountEmail && (
                <>
                  <label style={{ fontSize: '0.78rem', color: 'var(--muted)', marginBottom: 4, display: 'block' }}>
                    Service Account Email (share file with this):
                  </label>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    background: 'var(--bg)', padding: '8px 12px', borderRadius: 8,
                    fontFamily: 'monospace', fontSize: '0.85rem', wordBreak: 'break-all'
                  }}>
                    <span style={{ flex: 1 }}>{accessDenied.serviceAccountEmail}</span>
                    <CopyButton text={accessDenied.serviceAccountEmail} />
                  </div>
                </>
              )}
              <div className="flex gap-3 mt-3">
                <button className="btn btn-sm btn-primary" onClick={() => { setAccessDenied(null); detectSheets(); }}>
                  Retry
                </button>
                <button className="btn btn-sm btn-outline" onClick={() => setAccessDenied(null)}>
                  Dismiss
                </button>
              </div>
            </div>
          )}

          <button
            className="btn btn-primary"
            disabled={detecting || !canProceed}
            onClick={detectSheets}
          >
            {detecting ? (
              <>
                <span className="spinner" style={{ width: 18, height: 18 }} />
                {inputMode === 'drive' ? 'Checking Access & Detecting Sheets...' : 'Detecting Sheets...'}
              </>
            ) : (
              <>
                <FileSpreadsheet size={18} />
                Detect Sheets & Continue
              </>
            )}
          </button>
        </div>
      )}

      {/* Step 2: Mapping */}
      {step === 2 && (
        <div className="flex flex-col gap-4">
          <div className="message-info">
            <strong>Map each sheet to one or more couriers.</strong> One courier can only be assigned to one sheet.
            Sheets with the same commercials can be mapped to multiple couriers.
            {inputMode === 'drive' && driveFileName && (
              <div style={{ marginTop: 6, fontSize: '0.85rem', color: 'var(--muted)' }}>
                <HardDrive size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                Source: <strong>{driveFileName}</strong> (from Google Drive)
              </div>
            )}
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '35%' }}>Sheet Name</th>
                  <th>Status</th>
                  <th style={{ width: '50%' }}>Assigned Couriers</th>
                </tr>
              </thead>
              <tbody>
                {sheets.map(s => (
                  <tr key={s.name}>
                    <td style={{ fontWeight: 600 }}>
                      <div className="flex items-center gap-2">
                        <FileSpreadsheet size={16} style={{ color: s.valid ? 'var(--success)' : 'var(--danger)' }} />
                        {s.name}
                      </div>
                    </td>
                    <td>
                      {s.valid ? (
                        <span className="tag" style={{ background: 'var(--success-tint)', color: 'var(--success)', border: 'none' }}>Valid</span>
                      ) : (
                        <span className="tag" style={{ background: 'var(--danger-tint)', color: 'var(--danger)', border: 'none' }}>{s.error}</span>
                      )}
                    </td>
                    <td>
                      {s.valid ? (
                        <CourierMultiSelect
                          sheetName={s.name}
                          allCouriers={allCouriers}
                          selected={mapping[s.name] || []}
                          onSelect={handleCourierSelect}
                          assignedCouriers={assignedCouriers}
                        />
                      ) : (
                        <span className="text-muted text-sm">Skipped (invalid format)</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-3">
            <button className="btn btn-outline" onClick={() => setStep(1)}>
              Back
            </button>
            <button
              className="btn btn-primary"
              disabled={processing || !Object.values(mapping).some(v => v.length > 0)}
              onClick={() => processFile(false)}
            >
              {processing ? (
                <>
                  <span className="spinner" style={{ width: 18, height: 18 }} />
                  Processing & Uploading...
                </>
              ) : (
                'Process & Upload to Drive'
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Result */}
      {step === 3 && result && (
        <div className="flex flex-col gap-4">
          <div className="message-success">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={18} />
              <strong>Processing complete for {result.merchant_name}!</strong>
            </div>
          </div>
          <div className="result-card">
            <a href={result.input_file_link} target="_blank" rel="noopener noreferrer" className="result-link">
              <Link2 size={18} />
              Input File (Google Drive)
            </a>
            <a href={result.output_file_link} target="_blank" rel="noopener noreferrer" className="result-link">
              <Link2 size={18} />
              Output File (Google Drive)
            </a>
          </div>
          <button className="btn btn-primary" onClick={resetAll}>
            Process Another File
          </button>
        </div>
      )}

      {/* Warnings (zones without FWD rules) */}
      {warnings.length > 0 && !error && (
        <div className="message-warning mt-3">
          <div className="flex items-center gap-2" style={{ marginBottom: 8 }}>
            <AlertTriangle size={16} />
            <strong>Some zones have no FWD pricing rules. Do you want to continue?</strong>
          </div>
          <ul className="error-list" style={{ marginTop: 8 }}>
            {warnings.map((w, i) => (
              <li key={i} style={{ color: 'var(--warning)' }}>{w}</li>
            ))}
          </ul>
          <div className="flex gap-3 mt-3">
            <button className="btn btn-sm btn-primary" disabled={processing} onClick={() => processFile(true)}>
              {processing ? (
                <>
                  <span className="spinner" style={{ width: 16, height: 16 }} />
                  Processing...
                </>
              ) : (
                'Yes, Continue Anyway'
              )}
            </button>
            <button className="btn btn-sm btn-outline" onClick={() => setWarnings([])}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Errors */}
      {error && (
        <div className="message-error mt-3">
          <div className="flex items-center gap-2" style={{ marginBottom: validationErrors.length > 0 ? 8 : 0 }}>
            <AlertCircle size={16} />
            {error}
          </div>
          {validationErrors.length > 0 && (
            <ul className="error-list" style={{ marginTop: 8 }}>
              {validationErrors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
