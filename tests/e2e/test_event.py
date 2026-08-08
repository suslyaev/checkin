def test_admin_can_create_event_through_ui(ui_event):
    assert ui_event['id'] > 0
    assert ui_event['name'].startswith('Selenium Event ')
