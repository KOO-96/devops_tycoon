import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import './styles/tokens.css';
import './styles/reset.css';
import './styles/global.css';
import './styles/utilities.css';

const rootEl = document.getElementById('root');
if (rootEl === null) throw new Error('#root element not found');

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
