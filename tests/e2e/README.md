# UI tests

Run all UI tests in headless mode:

```powershell
python -m pytest tests\e2e -v
```

Show the browser and pause for two seconds after each action:

```powershell
$env:E2E_HEADLESS="0"
$env:E2E_SLOWMO="2"
python -m pytest tests\e2e\test_auth.py -v
```

Return to the normal fast headless mode:

```powershell
$env:E2E_HEADLESS="1"
$env:E2E_SLOWMO="0"
```

Run the guest search test in visible slow mode:

```powershell
$env:E2E_HEADLESS="0"
$env:E2E_SLOWMO="2"
python -m pytest tests\e2e\test_checkin.py::test_checker_can_find_guest_by_last_name -v
```

Run event creation through Django Admin in visible slow mode:

```powershell
$env:E2E_HEADLESS="0"
$env:E2E_SLOWMO="2"
python -m pytest tests\e2e\test_event.py -v
```

Run the check-in confirmation test in visible slow mode:

```powershell
python -m pytest tests\e2e\test_checkin.py::test_checker_can_confirm_guest -v
```

Each test creates real Django model records in a temporary pytest database.
The database is destroyed after the run, so hosted events are not changed.
