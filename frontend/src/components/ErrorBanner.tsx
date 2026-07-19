interface Props {
  error: string | null;
  warnings: string[];
  onDismiss: () => void;
}

export function ErrorBanner({ error, warnings, onDismiss }: Props) {
  if (!error && warnings.length === 0) return null;
  return (
    <div className={"banner " + (error ? "banner-error" : "banner-warn")}>
      <div className="banner-body">
        {error && <strong>{error}</strong>}
        {!error && warnings.length > 0 && (
          <>
            <strong>Trace completed with {warnings.length} warning(s)</strong>
            <ul>
              {warnings.slice(0, 5).map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </>
        )}
      </div>
      <button className="banner-close" onClick={onDismiss} aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}
