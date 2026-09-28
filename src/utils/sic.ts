// Scientific WMO Standard Sea Ice Classification Helper
export const getSicInfo = (sic: number) => {
  const pct = sic <= 1.0 ? sic * 100 : sic;
  if (pct >= 80) return { label: '80–100% (Fast Ice)', thickness: '2.0–3.2m', color: '#FFFFFF', stroke: '#FFFFFF', risk: 'CRITICAL', riskColor: '#EF4444' };
  if (pct >= 50) return { label: '50–80% (Pack Ice)', thickness: '1.2–1.8m', color: '#00D8F6', stroke: '#00F2FE', risk: 'HIGH', riskColor: '#F97316' };
  if (pct >= 15) return { label: '15–50% (Marginal Ice)', thickness: '0.3–0.9m', color: '#0284C7', stroke: '#0284C7', risk: 'MODERATE', riskColor: '#F59E0B' };
  return { label: 'Open Ocean (<15%)', thickness: '0.0m', color: '#03172B', stroke: '#38BDF8', risk: 'SAFE', riskColor: '#38BDF8' };
};
