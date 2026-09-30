export type SignalCoverage = {
  total: number;
  covered: number;
  uncovered: number;
  percentage: number;
};

export function signalCoverage(instrumentsTotal: number, signalsTotal: number): SignalCoverage {
  const total = Math.max(0, Math.trunc(Number.isFinite(instrumentsTotal) ? instrumentsTotal : 0));
  const covered = Math.min(total, Math.max(0, Math.trunc(Number.isFinite(signalsTotal) ? signalsTotal : 0)));
  return {
    total,
    covered,
    uncovered: total - covered,
    percentage: total ? Math.round((covered / total) * 1000) / 10 : 0,
  };
}
