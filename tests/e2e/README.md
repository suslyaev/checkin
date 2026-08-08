# UI tests

The UI tests run only against the persistent `testAnis` environment:

```text
http://62.113.111.146:8001
```

The test suite refuses to run against another host or port. Tests create
numbered events, contacts, and registrations through the UI. These records
stay in the persistent `testAnis` database after the run. Existing records are
never deleted. New names look like `Selenium Event 0001` and
`Selenium Guest 0001`.

Set the credentials for the `testAnis` superuser in the current PowerShell
session. Do not add them to Git or to this file:

```powershell
$env:E2E_PHONE="+79990000001"
$env:E2E_PASSWORD="your-test-password"
```

Run all UI tests in headless mode:

```powershell
$env:E2E_HEADLESS="1"
$env:E2E_SLOWMO="0"
python -m pytest tests\e2e -v
```

Show the browser and pause for two seconds after each supported action:

```powershell
$env:E2E_HEADLESS="0"
$env:E2E_SLOWMO="2"
python -m pytest tests\e2e -v
```

Run event creation through Django Admin:

```powershell
python -m pytest tests\e2e\test_event.py -v
```

Run the guest search scenario:

```powershell
python -m pytest tests\e2e\test_checkin.py::test_checker_can_find_guest_by_last_name -v
```

Run the check-in confirmation scenario:

```powershell
python -m pytest tests\e2e\test_checkin.py::test_checker_can_confirm_guest -v
```

Clear credentials from the current PowerShell session when finished:

```powershell
Remove-Item Env:E2E_PHONE
Remove-Item Env:E2E_PASSWORD
```
