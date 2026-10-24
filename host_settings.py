"""Validated chat transactions for session fields and applied comparisons."""
from dataclasses import asdict
from uuid import uuid4

from engine import Scenario

FIELDS = tuple(asdict(Scenario()))
LABELS = dict(bankroll='Bankroll', target='Profit target', loss_limit='Loss limit',
              minimum='Minimum bet', maximum='Maximum wager', chip='Chip size',
              spins='Spin limit', wheel='Wheel / rules')


def prepare_settings_update(context, changes, *, apply=False):
    """Prepare one allowlisted transaction; no UI/session state is written here."""
    if not isinstance(context, dict) or set(context.get('values', {})) != set(FIELDS):
        raise ValueError('Settings editing is available only from the app chat.')
    if not isinstance(changes, dict) or (not changes and not apply) or set(changes) - set(FIELDS):
        raise ValueError('Supply only the session settings you want to change.')
    if context.get('proposal'):
        raise ValueError('Only one settings update is allowed per reply.')
    before = dict(context['values'])
    after = asdict(Scenario(**{**before, **changes}))
    changed = [dict(field=k, before=before[k], after=after[k])
               for k in FIELDS if before[k] != after[k]]
    if not changed and not apply:
        return dict(status='no_changes', message='Those values are already in Step 1.')
    context['proposal'] = dict(id=uuid4().hex, before=before, after=after, changes=changed,
                               action='apply' if apply else 'edit')
    return dict(status='ready_for_ui', changes=changed,
                message=('The app will apply these settings and display the comparison if the form is still unchanged. '
                         'Existing sessions keep their original limits and logs; selecting a system starts a new tracker.'
                         if apply else 'The app will update the Step 1 fields if they are still unchanged. '
                        'The user then clicks Apply settings & continue to recalculate. '
                        'Existing tracked, practice and free-play sessions are untouched.'))


def commit_settings_update(proposal, current):
    """Revalidate at receipt time and avoid overwriting edits made while AI thought."""
    if not isinstance(proposal, dict) or not isinstance(proposal.get('id'), str):
        raise ValueError('Invalid settings update.')
    before, after = proposal.get('before'), proposal.get('after')
    action = proposal.get('action', 'edit')
    if action not in ('edit', 'apply'):
        raise ValueError('Unknown settings action.')
    if not isinstance(before, dict) or not isinstance(after, dict) or \
            set(before) != set(FIELDS) or set(after) != set(FIELDS):
        raise ValueError('Only Step 1 session fields can be changed.')
    validated = asdict(Scenario(**after))
    if current != before:
        raise ValueError('Your settings changed while I was responding. '
                         'I kept your latest values; ask again using those settings.')
    changes = [dict(field=k, before=before[k], after=validated[k])
               for k in FIELDS if before[k] != validated[k]]
    if not changes and action != 'apply':
        raise ValueError('Those values are already in Step 1.')
    return validated, dict(id=proposal['id'], status='updated', changes=changes, action=action)


def undo_settings_update(snapshot, current_fields, current_applied):
    """Undo one committed transaction without overwriting a newer manual change."""
    if not isinstance(snapshot,dict) or snapshot.get('action') not in ('edit','apply'):
        raise ValueError('No settings change is available to undo.')
    if current_fields!=snapshot.get('after_fields') or current_applied!=snapshot.get('after_applied'):
        raise ValueError('Newer settings changes are present. I kept them unchanged; Undo cannot overwrite them.')
    before=snapshot.get('before_fields')
    if not isinstance(before,dict) or set(before)!=set(FIELDS):
        raise ValueError('The previous form snapshot is invalid.')
    # Restore even an unfinished form draft faithfully. Only applied settings
    # must be valid calculator inputs.
    applied=asdict(Scenario(**snapshot['before_applied']))
    return dict(before),applied
