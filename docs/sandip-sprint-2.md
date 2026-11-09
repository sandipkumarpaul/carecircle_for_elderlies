# Sandip Sprint 2 — CC-18 Health alert centre

This increment adds one assessed feature on top of the whole team's Sprint 1. Existing care circles, medicine workflows, dose schedules and vitals remain included. Authentication remains supporting functionality.

## Behaviour

The selected patient's feed contains only alerts originally addressed to the signed-in user, filtered again by their current alerts and source-data permissions. Critical alerts precede warnings and information; newest comes first within each severity, with a stable ID tie-breaker. Status, severity and unread filters apply before pagination. Granting access later does not retroactively create recipient records for old alerts.

Mark read changes only that recipient's read timestamp. Acknowledge changes an open alert to acknowledged; resolve closes an open or acknowledged alert. These two actions require alerts:write as well as source read access and recipient membership. All current recipients see the shared lifecycle status. Repeated actions do not rewrite timestamps or duplicate lifecycle audit records, and an acknowledged or resolved alert cannot be reopened through these endpoints. Neither action changes the underlying health record or certifies medical recovery.

Acknowledgement/resolution cancels all pending deliveries for the alert. The shared pre-dispatch gate also rejects later escalation rows for closed alerts and rechecks current permissions. An email already dispatched cannot be recalled.

Each user can configure their own quiet hours per patient, with an IANA timezone. Noncritical email deliveries are deferred until the quiet period ends; critical alerts bypass quiet hours, and in-app visibility is unaffected. Overnight periods and DST gaps/overlaps are handled. Start equals end is rejected; clearing both times disables quiet hours. Read-only alert recipients can manage their personal preferences, but cannot acknowledge or resolve alerts.

## MVC and endpoints

- Model: existing Alert/AlertRecipient/Delivery; new nullable lifecycle fields and AlertPreference in models/identity.py. Additive migration 0005_sandip follows 0004_tasin.
- Controller: controllers/alerts.py handles verified sessions, CSRF, validated filters, patient locks and transaction completion.
- Service: services/alert_center.py owns feed filtering, lifecycle, audit and preferences; services/alerts.py retains the shared raise-alert contract and implements pre-dispatch quiet-hour/state checks.
- View: views/alerts/AlertCenter.tsx displays the feed, filters, actions and personal quiet hours using the shared API client.

All paths begin `/api/v1/patients/{patient_id}`:

| Method/path | Contract |
|---|---|
| GET /alerts | status, severity, unread, offset, limit (default 20, maximum 100); items/total/offset/limit envelope |
| POST /alerts/{alert_id}/read | Personal read state; alerts:read plus source scope |
| POST /alerts/{alert_id}/acknowledge | Shared lifecycle; alerts:write plus source scope |
| POST /alerts/{alert_id}/resolve | Shared lifecycle; alerts:write plus source scope |
| GET /alert-preferences | Current user's settings for this patient |
| PUT /alert-preferences | timezone, quiet_start and quiet_end (HH:MM or both null); no arbitrary user ID |

Actions are serialized by the existing patient lock. Internal callers of delivery_allowed must hold the same lock, pass/recheck the current dispatch time immediately before sending, and commit any due_at deferral. The gate does not send messages. The backend never exposes an arbitrary public raise-alert endpoint.

## Faculty demonstration

1. Log in as a patient and select their profile. Under Vitals, use demonstration limits and save a synthetic out-of-range reading. This creates a real internal alert through Saif's feature.
2. In Health alert centre, click Refresh alerts. Review the alert's severity, status and time. Review vitals links back to the source module.
3. Mark it read, select Unread alerts only and refresh: it disappears from that filtered view. Clear the filter and refresh again.
4. Acknowledge the alert, then resolve it. Reload: the final status and timestamps persist.
5. Set quiet hours, for example 22:00–07:00 in Asia/Dhaka. Save, reload and verify persistence. Disable quiet hours to clear the setting.
6. Before creating a second alert, invite a caregiver with View alerts and View vitals. Accept the invitation, then create another out-of-range reading. The caregiver can read that alert but cannot acknowledge/resolve it until Manage alerts is granted. Removing View vitals hides the source alert; revocation prevents further access.

## Boundaries

The UI refreshes on opening or explicit Refresh alerts; it is not a live push-notification system. Saif's vitals supply real current alerts; other alert producers remain owned by their respective features. SMTP delivery, delivery leases/retries, automatic escalation workers, SOS and emergency contacts are not implemented by CC-18. Quiet-hour and cancellation policies are tested at the durable delivery boundary without claiming that emails were sent. No seeded credentials or automatic clinical approvals are included.
