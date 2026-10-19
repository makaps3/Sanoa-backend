# Sanoa verification and release guide

## Implemented policy

Sanoa now follows the Sanoa Plus principle of explicit onboarding access and current database approval for operational access. Uploaded evidence is not approval. The server makes the decision, and the mobile app shows the verification workspace until access is granted.

- Individuals: identity number, ID document, selfie with ID, proof of address, trading name, payout account and bank proof. CIPC is optional and remains uploadable.
- Businesses: owner identity and address evidence, trading name, CIPC registration number and certificate, payout account and bank proof. CIPC is compulsory. Tax clearance remains optional.
- Drivers: required identity, licence, vehicle and insurance evidence, accepted terms, current licence dates, verified email, and approved identity AND background review.
- Vendor submissions must be complete before review. Approval requires an active, email-verified account. Rejection and requests for more information retain reviewer notes. Review decisions are audited.
- Replacing material identity, business or banking evidence resets approval. Suspension is preserved. Legacy profiles and their vetting records follow the unified vendor profile.
- JWT, session and API-token requests use the same operational gate. WebSockets check current approval on connection and messages. Existing credentials cannot preserve revoked operational access.
- Only invited admins may register publicly; only a superuser may directly create an admin profile. Suspended reviewers cannot approve applicants. Profile updates cannot change account roles or verification flags.
- Admin invitations send a real transactional email with an acceptance token. Failed delivery rolls back the invitation so the sender can retry. Expired invitations can be replaced even after the intended admin has registered. The mobile onboarding screen accepts the invitation instead of allowing applicants to select their own roles.

## API credentials and contracts

API-token secrets are returned once, in the creation response with `Cache-Control: no-store`. Lists and detail responses expose only metadata and the display prefix. The database stores a SHA-256 hash, never the raw secret. Existing issued credentials continue to authenticate using their existing hashes after migration `accounts.0015`; integrations that previously fetched secrets from token listings must retain their creation response or issue a replacement.

Token scopes are enforced in authentication before a view runs: `read` permits safe HTTP methods only; `products`, `orders` and `inventory` permit only views belonging to that application; `full` permits all API areas subject to the user's existing permissions and verification. Scoped credentials cannot create broader credentials. Unknown scopes fail closed. Revoked, expired and inactive-user credentials are refused. Malformed headers return authentication errors, and usage records use the connection peer rather than untrusted forwarded IP headers.

OpenAPI describes JWT, session cookies and the two alternative API-token headers. Vendor/driver self-service status, submission and document-upload endpoints describe their actual checklist and result shapes, including binary uploads and error responses. The optional individual CIPC requirement remains an item-level checklist flag.

## Documents

Evidence accepts PDF, JPEG or PNG up to 10 MB, with content checks. Evidence URLs now use authenticated `/api/accounts/documents/` downloads. Owners and authorized reviewers can read them. Flutter previews use bearer authentication, same-origin requests and memory buffers.

Existing physical files remain in `MEDIA_ROOT`; migrations change storage behavior without moving files. **The production proxy and any CDN must deny public access to the private prefixes.** Adapt `nginx-private-media.conf.example`, including its warning about `^~` locations. Disable any prior public bucket/CDN exposure and purge cached evidence. Public avatars and storefront images remain public. The application validates file formats but does not provide an antivirus scanning service.

## Mobile design and configuration

The Flutter source under `Documents/Frontend Projects/Sanoa/sanoa` uses solid surfaces, shared round buttons and circular icon controls. The four role profiles have consistent status panels. Vendor and driver operational dashboards are mounted only after server approval; errors provide retry and sign-out paths. Private evidence has an authenticated preview.

All seven font families used by the app are bundled locally (88 variants with their open-font licenses), and runtime font downloads are disabled. `tool/bundle_fonts.py` verifies font hashes against the installed `google_fonts` package metadata. The Android build skips Jetifier rewriting for native-only Flutter engine JARs and limits Gradle to one worker to reduce memory pressure on this workstation.

Development defaults to the Android emulator at `http://10.0.2.2:8101`. Supply `--dart-define=API_BASE_URL=https://your-server` for a physical device or another server. Release mode requires an explicit HTTPS origin and rejects ngrok hosts. Android production builds disable cleartext traffic; debug builds allow local HTTP.

Maps configuration:

- Dart: `--dart-define=GOOGLE_MAPS_API_KEY=...` for existing Dart map services.
- Android: `GOOGLE_MAPS_ANDROID_API_KEY` environment variable when building; restrict this key to the application ID and signing certificate.
- iOS: `GOOGLE_MAPS_IOS_API_KEY` Xcode build setting; restrict it to the bundle ID.

Android release signing uses `android/key.properties` with `storeFile`, `storePassword`, `keyAlias`, and `keyPassword`. The keystore path is relative to the Android project or absolute. These files are ignored by Git. A release build without a signing configuration fails instead of using the debug certificate.

Example release command (replace the origin and configure maps/signing first):

```powershell
flutter build appbundle --release --dart-define=API_BASE_URL=https://api.example.com --dart-define=GOOGLE_MAPS_API_KEY=YOUR_RESTRICTED_KEY
```

## Deployment

1. Back up the database and media; review existing verified accounts for missing evidence and expired driver licences. Driver background checks previously left pending will now prevent operational access until reviewed.
2. Configure `.env.production.example` values through deployment secrets. Use PostgreSQL, Redis, SMTP, HTTPS, explicit allowed hosts and CORS origins. Generate a unique Django secret. Previously embedded SMTP, payment and maps credentials must be rotated/restricted; removal from current source does not revoke them.
3. Apply the private-media proxy rules before exposing the new deployment. Only enable `TRUST_PROXY_SSL_HEADER` behind a proxy that replaces incoming forwarded headers.
4. With production configuration loaded, run:

   ```text
   python manage.py check --deploy
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   ```

   New migrations: business `0018` and delivery `0011` configure private evidence storage; accounts `0015` removes stored plaintext API-token secrets while retaining hashes. Back up the database and deploy the credential code and migration together. Do not fake these migrations. No migrations have been applied to the user's live database by this task.
5. Run the ASGI service, Redis and the project's Celery workers/scheduler. The Docker image now runs Daphne as a non-root user; provision writable media/log/static volumes for that user. Static collection is an explicit release step and failures are no longer hidden during image build.
6. Run staging acceptance tests with real SMTP and payment sandbox credentials: OTP delivery, invitation acceptance, individual signup without CIPC, business signup with CIPC, payout setup, uploads/previews, submit, request corrections, resubmit, approve, operate, replace evidence, suspend and retry the same token. Test driver approval in both queues and expired licences. Confirm that other users and public media URLs cannot fetch evidence.

## Validation and limits

Verified locally: the full 128-test backend regression suite passes, including invitation delivery/acceptance/expiry, token scope enforcement, one-time secret disclosure, token ownership/revocation, malformed credentials and verification API contracts. Two existing Django constraint-deprecation warnings remain. Five Flutter checks (including the offline phone-sized visual render) also passed in the preceding mobile validation. Django's normal system check passes and `makemigrations --check --dry-run` reports no pending model changes. Whole-app Flutter analysis reports no errors; legacy warnings/info remain. The final admin onboarding integration was also analyzed separately without errors.

The ARM64 debug Android build succeeded using `flutter build apk --debug --no-pub --target-platform android-arm64`. Its output is `build/app/outputs/flutter-apk/app-debug.apk` in the mobile project. This is a development artifact, not a signed store release. It uses the default emulator backend address; rebuild with the appropriate `API_BASE_URL` for a physical device or staging environment. The actual invitation-screen preview at `build/review/admin-invitation.png` was visually inspected after fonts were bundled and button typography was corrected.

The production-settings check runs with synthetic PostgreSQL/SMTP configuration. Authentication extensions and self-service verification contracts reduced its reported issues from 1,170 to 363 (`logs/deployment-security-check.log`). It still reports other API-schema warnings (missing serializer declarations, schema-generation fallbacks and database-dependent inspection) and the intentional HSTS preload warning. Those warnings have not been hidden or presented as a clean production release check. PostgreSQL adapter 2.9.10 was installed locally and pinned for Python 3.13 compatibility; see its [published package metadata](https://pypi.org/project/psycopg2-binary/2.9.10/).

The latest full backend regression result is recorded in `logs/regression-security.log`; earlier results are in `logs/verification-final.log` and `logs/invitation-tests.log`. Flutter regression/render results are in `visual-review.log`, static analysis in `analysis-release.log` and `analysis-onboarding.log`, and successful Android compilation in `build-verification.log` in the mobile project. This backend continuation did not change the mobile source. Regression tests use SQLite; exercise concurrent submissions/reviews on staging PostgreSQL before release.

This work does not deploy services, provision credentials, deliver real OTP emails, execute live payments, sign a store release, or validate iOS on macOS. Existing Flutter analyzer warnings and unrelated feature flows need separate review. Fraud-scoring and notification threads now start after transaction commit, but remain best-effort background work; durable delivery/retry is not guaranteed by those threads. A production launch requires the staging checks above and operational monitoring/backups.
