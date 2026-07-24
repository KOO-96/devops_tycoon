/** Shows when a command was applied on the backend but the follow-up snapshot
 * sync failed (§7). Offers a refresh that re-fetches the snapshot (never re-sends
 * the command). */

import { useController } from '../../session/controllerContext';
import { useGameSessionStore } from '../../state/gameSessionStore';

export function SnapshotSyncBanner(): JSX.Element | null {
  const syncState = useGameSessionStore((s) => s.snapshotSyncState);
  const controller = useController();
  if (syncState !== 'failed') return null;
  return (
    <div className="banner banner-warn" role="alert" aria-live="assertive">
      Command applied, but the board could not be refreshed.{' '}
      <button
        type="button"
        onClick={() => {
          void controller.retrySnapshotSync();
        }}
      >
        Refresh board
      </button>
    </div>
  );
}
