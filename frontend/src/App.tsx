import React, { useState, useEffect } from 'react';
import { LandingPage } from './pages/LandingPage';
import { DashboardPage } from './pages/DashboardPage';
import { BandPreviewPage } from './pages/BandPreviewPage';

interface RouteState {
  name: 'landing' | 'dashboard' | 'band-preview';
  sceneId?: string;
  band?: string;
}

const parseRoute = (): RouteState => {
  const full = window.location.pathname + window.location.hash;

  // Match /band-preview/:sceneId/:band
  const bandMatch = full.match(/band-preview\/([^/?#]+)\/([^/?#]+)/);
  if (bandMatch) {
    return {
      name: 'band-preview',
      sceneId: decodeURIComponent(bandMatch[1]),
      band: decodeURIComponent(bandMatch[2]),
    };
  }

  if (full.includes('/dashboard')) {
    return { name: 'dashboard' };
  }

  return { name: 'landing' };
};

export const App: React.FC = () => {
  const [route, setRoute] = useState<RouteState>(parseRoute);

  useEffect(() => {
    const handleLocationChange = () => {
      setRoute(parseRoute());
    };

    window.addEventListener('popstate', handleLocationChange);
    window.addEventListener('hashchange', handleLocationChange);
    return () => {
      window.removeEventListener('popstate', handleLocationChange);
      window.removeEventListener('hashchange', handleLocationChange);
    };
  }, []);

  const navigate = (path: string) => {
    try {
      window.history.pushState({}, '', path);
    } catch {
      window.location.hash = path;
    }
    setRoute(parseRoute());
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleBackFromPreview = () => {
    // If the browser has history stack from the dashboard, use history.back()
    // otherwise fallback to /dashboard
    if (window.history.length > 1) {
      window.history.back();
    } else {
      navigate('/dashboard');
    }
  };

  if (route.name === 'band-preview' && route.sceneId && route.band) {
    return (
      <BandPreviewPage
        sceneId={route.sceneId}
        band={route.band}
        onBack={handleBackFromPreview}
      />
    );
  }

  if (route.name === 'dashboard') {
    return (
      <DashboardPage
        onGoHome={() => navigate('/')}
        onSelectBand={(sceneId, band) =>
          navigate(`/band-preview/${encodeURIComponent(sceneId)}/${encodeURIComponent(band)}`)
        }
      />
    );
  }

  return <LandingPage onLaunchDashboard={() => navigate('/dashboard')} />;
};

export default App;
