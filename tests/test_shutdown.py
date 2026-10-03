"""Exercise actual controller methods without requiring a running HA installation."""
import ast
import asyncio
import logging
from pathlib import Path
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

source = Path('custom_components/ecoflow_solar_surplus/controller.py').read_text()
tree = ast.parse(source)
controller = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'EcoFlowSurplusController')
methods = [n for n in controller.body if getattr(n, 'name', '') in {'_force_states', '_async_verify_stop', 'async_handle_trigger'}]
module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), ast.ClassDef(name='Controller', bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
namespace = {'datetime': datetime, 'UTC': UTC, '_LOGGER': logging.getLogger('test'), 'HomeAssistantError': RuntimeError, 'MODE_OBSERVE': 'observe'}
exec(compile(ast.fix_missing_locations(module), '<actual controller methods>', 'exec'), namespace)
Controller = namespace['Controller']

class ShutdownTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.c = Controller()
        self.c.force_entities = ('a', 'b', 'c')
        self.states = {'a': 'on', 'b': 'off', 'c': 'off'}
        self.c.hass = SimpleNamespace(states=SimpleNamespace(get=lambda e: SimpleNamespace(state=self.states[e])))
        self.c.command = SimpleNamespace(mask=0, owned=True)
        self.c._stop_status = 'not_requested'
        self.c._stop_attempts = 0
        self.c._stop_last_at = None
        self.c._last_error = None
        self.c._async_turn_off_all = AsyncMock()
        self.c._async_set_command_state = AsyncMock()
        self.c._record_action = lambda action: setattr(self.c, 'action', action)
        self.snapshot = SimpleNamespace(shp_power_ok=True, physical_charge_w=1102, daylight=False, site_grid_ok=True, solar_ok=True, soc_ok=True, solar_w=0, eligible_count=3)
        self.settings = SimpleNamespace(minimum_rate_w=500, minimum_solar_w=150)

    async def stop(self):
        await self.c._async_verify_stop(self.snapshot, self.settings)

    async def test_off_command_with_actual_charging_is_corrected(self):
        await self.stop()
        self.c._async_turn_off_all.assert_awaited_once()
        self.assertEqual(self.c._stop_status, 'awaiting_confirmation')

    async def test_switches_off_but_physical_charging_still_retries(self):
        self.states.update(dict.fromkeys(self.states, 'off'))
        await self.stop()
        self.c._async_turn_off_all.assert_awaited_once()

    async def test_no_flood_and_bounded_retries(self):
        await self.stop()
        for _ in range(50): await self.stop()
        self.assertEqual(self.c._async_turn_off_all.await_count, 1)
        for _ in range(3):
            self.c._stop_last_at -= timedelta(seconds=31)
            await self.stop()
        self.assertEqual(self.c._async_turn_off_all.await_count, 3)
        self.assertEqual(self.c._stop_status, 'unconfirmed')
        self.assertIsNotNone(self.c._last_error)

    async def test_confirmation_requires_switches_and_power(self):
        await self.stop()
        self.snapshot.physical_charge_w = 0
        await self.stop()
        self.assertNotEqual(self.c._stop_status, 'confirmed')
        self.states.update(dict.fromkeys(self.states, 'off'))
        await self.stop()
        self.assertEqual(self.c._stop_status, 'confirmed')

    async def test_unavailable_switch_cannot_confirm(self):
        self.states.update(dict.fromkeys(self.states, 'off'))
        self.states['a'] = 'unavailable'
        self.snapshot.physical_charge_w = 0
        await self.stop()
        self.assertNotEqual(self.c._stop_status, 'confirmed')

    async def test_confirmed_idle_does_not_write_or_retry(self):
        self.states.update(dict.fromkeys(self.states, 'off'))
        self.snapshot.physical_charge_w = 0
        for _ in range(50): await self.stop()
        self.c._async_turn_off_all.assert_not_awaited()
        self.c._async_set_command_state.assert_not_awaited()

    async def test_stale_physical_power_cannot_confirm(self):
        self.states.update(dict.fromkeys(self.states, 'off'))
        self.snapshot.physical_charge_w = 0
        self.snapshot.shp_power_ok = False
        await self.stop()
        self.assertNotEqual(self.c._stop_status, 'confirmed')

    async def test_later_recurrence_gets_new_retry_budget(self):
        self.c._stop_status = 'confirmed'
        self.c._stop_attempts = 3
        await self.stop()
        self.assertEqual(self.c._stop_attempts, 1)
        self.c._async_turn_off_all.assert_awaited_once()

    async def test_service_failure_keeps_verification_pending(self):
        self.c._async_turn_off_all.side_effect = RuntimeError('timeout')
        with self.assertRaises(RuntimeError): await self.stop()
        self.assertEqual(self.c._stop_attempts, 1)
        self.c._async_set_command_state.assert_not_awaited()

    async def trigger(self, mode='control', trigger='grid'):
        c = self.c
        c.operating_mode = mode
        c.is_control_mode = mode == 'control'
        c._lock = asyncio.Lock()
        c._snapshot = lambda: self.snapshot
        c._effective_settings = lambda: self.settings
        c._normalize_command_rate = lambda _: None
        c._evaluate_physical_recovery_timer = lambda: None
        c._notify = lambda: None
        c._sync_observed_command_state = lambda: None
        c._async_handle_grid = AsyncMock()
        c._async_handle_reassert = AsyncMock()
        await c.async_handle_trigger(trigger)

    async def test_nighttime_grid_guard_preempts_held_command(self):
        await self.trigger()
        self.c._async_turn_off_all.assert_awaited_once()
        self.c._async_handle_grid.assert_not_awaited()

    async def test_nighttime_reassert_cannot_turn_charging_back_on(self):
        self.c.command.mask = 1
        await self.trigger(trigger='reassert')
        self.c._async_handle_reassert.assert_not_awaited()
        self.c._async_turn_off_all.assert_awaited_once()

    async def test_observe_mode_has_no_actuator_calls(self):
        await self.trigger(mode='observe')
        self.c._async_turn_off_all.assert_not_awaited()
        self.c._async_handle_grid.assert_awaited_once()

class ShutdownHistoryTests(IsolatedAsyncioTestCase):
    async def test_routine_grid_decisions_do_not_evict_shutdown_events(self):
        from collections import deque
        src = ast.parse(Path('custom_components/ecoflow_solar_surplus/observability.py').read_text())
        cls = next(n for n in src.body if isinstance(n, ast.ClassDef))
        method = next(n for n in cls.body if getattr(n, 'name', '') == '_refresh')
        mod = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), ast.ClassDef(name='History', bases=[], keywords=[], body=[method], decorator_list=[])], type_ignores=[])
        ns = {'datetime': datetime}
        exec(compile(ast.fix_missing_locations(mod), '<actual history method>', 'exec'), ns)
        h = ns['History']()
        data = {'snapshot': {'physical_charge_w': 1102}, 'decision': {}, 'command': {'mask': 0}, 'last_trigger': 'grid', 'shutdown_verification': {'status': 'awaiting_confirmation', 'attempts': 1, 'last_request_at': '2026-10-03T01:42:00+00:00'}, 'force_charge_states': {'a': 'on'}}
        h.controller = SimpleNamespace(diagnostic_data=lambda: data)
        h._shutdown_history = deque(maxlen=50)
        h._history = deque(maxlen=50)
        h._last_shutdown_signature = None
        h._last_seen_grid_action_at = None
        h._last_command = {}
        h._session_started_at = datetime.now(UTC)
        for i in range(200):
            data['last_action_at'] = (h._session_started_at + timedelta(seconds=i)).isoformat()
            h._refresh(record_history=True)
        self.assertEqual(len(h._history), 50)
        self.assertEqual(len(h._shutdown_history), 1)
        self.assertEqual(h._shutdown_history[0]['force_charge_states'], {'a': 'on'})
        data['shutdown_verification'] = {**data['shutdown_verification'], 'status': 'unconfirmed', 'attempts': 3}
        h._refresh(record_history=True)
        self.assertEqual(len(h._shutdown_history), 2)
