/** Route table (§3 routing). */

import { Route, Routes } from 'react-router-dom';
import { StartPage } from '../pages/StartPage';
import { GamePage } from '../pages/GamePage';
import { NotFoundPage } from '../pages/NotFoundPage';

export function AppRoutes(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<StartPage />} />
      <Route path="/game/:sessionId" element={<GamePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
