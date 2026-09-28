import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { FleetProvider } from './context/FleetContext';
import Landing from './pages/Landing';
import OverviewPage from './pages/platform/OverviewPage';
import NavigationPage from './pages/platform/NavigationPage';
import SeaIcePage from './pages/platform/SeaIcePage';
import IcebergTrackingPage from './pages/platform/IcebergTrackingPage';
import AnalysisPage from './pages/platform/AnalysisPage';
import RouteOptimizationPage from './pages/platform/RouteOptimizationPage';
import AlertsPage from './pages/platform/AlertsPage';
import ReportsPage from './pages/platform/ReportsPage';
import IntelligencePage from './pages/platform/IntelligencePage';
import HistoricalVoyagePage from './pages/platform/HistoricalVoyagePage';
import LiveDataPage from './pages/platform/LiveDataPage';
import OperationsConsole from './pages/OperationsConsole';

function App() {
  return (
    <Router>
      <FleetProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/operations" element={<OperationsConsole />} />
          <Route path="/navigation" element={<NavigationPage />} />
          <Route path="/telemetry" element={<Navigate to="/navigation" replace />} />
          <Route path="/sea-ice" element={<SeaIcePage />} />
          <Route path="/icebergs" element={<IcebergTrackingPage />} />
          <Route path="/routes" element={<RouteOptimizationPage />} />
          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/historical-validation" element={<HistoricalVoyagePage />} />
          <Route path="/live-data" element={<LiveDataPage />} />
          <Route path="/platform" element={<Navigate to="/overview" replace />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </FleetProvider>
    </Router>
  );
}

export default App;
