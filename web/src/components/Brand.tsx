/** CityVision mark: a city block seen from above, inside a camera reticle. */
export function BrandMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className="brand-mark">
      <path d="M3 8V4.5A1.5 1.5 0 0 1 4.5 3H8M16 3h3.5A1.5 1.5 0 0 1 21 4.5V8M21 16v3.5a1.5 1.5 0 0 1-1.5 1.5H16M8 21H4.5A1.5 1.5 0 0 1 3 19.5V16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <rect x="7.5" y="7.5" width="4" height="4" rx="0.8" fill="currentColor" />
      <rect x="12.5" y="7.5" width="4" height="4" rx="0.8" fill="currentColor" opacity="0.55" />
      <rect x="7.5" y="12.5" width="4" height="4" rx="0.8" fill="currentColor" opacity="0.55" />
      <circle cx="14.5" cy="14.5" r="2" fill="currentColor" />
    </svg>
  );
}

export function Brand({ large = false }: { large?: boolean }) {
  return (
    <span className={`brand ${large ? "brand-lg" : ""}`}>
      <BrandMark size={large ? 28 : 22} />
      <span className="brand-name">
        City<span>Vision</span>
      </span>
    </span>
  );
}
