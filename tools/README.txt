MAINTENANCE SCRIPTS
=========================================================

Things you need rarely. They work exactly like the scripts in the
project root, just kept out of the way - the root holds only the
four files you use all the time.

diagnose-deploy.bat
   If deploy-to-server.bat complains about permissions or files -
   run this. It shows the cause within a minute.

create-admin.bat
   A new admin account. Needed if you forget the password.
   You type the password yourself; never send it in a chat.

test-telegram.bat
   Sends a test notification. Useful when orders stopped arriving
   in Telegram and you need to find where the chain breaks.

run-checks.bat
   Full check: manage.py check, migrations, translations, tests.
   Run after any code change, before deploying to the server.
   All green - safe to deploy.

seed-demo.bat
   Fills an EMPTY database with demo bouquets, categories and pages.
   Existing products are not touched. Not needed on the live database.
