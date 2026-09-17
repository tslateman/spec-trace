const timezoneSuffix = /(Z|[+-]\d{2}:?\d{2})$/i;

export function isoformat(stored: string): string {
  return `${stored.replace(" ", "T")}+00:00`;
}

export function storedFrom(date: Date): string {
  const iso = date.toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 23)}000`;
}

export function storedNow(): string {
  return storedFrom(new Date());
}

export function parseDatetime(value: string): Date | undefined {
  const normalised = value.trim().replace(" ", "T");
  const withZone = timezoneSuffix.test(normalised) ? normalised : `${normalised}Z`;
  const date = new Date(withZone);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

export function roundHalfEven(value: number, digits: number): number {
  const scale = 10 ** digits;
  const scaled = value * scale;
  const floor = Math.floor(scaled);
  const fraction = scaled - floor;
  const rounded = fraction === 0.5 ? (floor % 2 === 0 ? floor : floor + 1) : Math.round(scaled);
  return rounded / scale;
}
