from types import SimpleNamespace
from unittest.mock import Mock
import ic382_navigation.events as implementation

def event_stream(monkeypatch):
    clock=[0.]
    monkeypatch.setattr(implementation.time,'monotonic',lambda:clock[0])
    node=SimpleNamespace(create_publisher=lambda *a:Mock(),get_name=lambda:'desk_navigation',
        get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=0)),get_logger=lambda:Mock())
    return implementation.Events(node,'first'),clock

def test_new_event_after_long_idle_does_not_timeout_immediately(monkeypatch):
    events,clock=event_stream(monkeypatch)
    events.emit('arrived',{});assert events.pending_age(1,10.)==0.
    clock[0]=30.;events.emit('next_target',{})
    assert events.pending_age(1,30.)==0.
    assert events.pending_age(1,34.9)<5.
    assert events.pending_age(1,35.1)>5.,'A genuinely unacknowledged event must still time out'

def test_oldest_unacknowledged_event_owns_deadline(monkeypatch):
    events,clock=event_stream(monkeypatch)
    events.emit('first',{});clock[0]=4.;events.emit('second',{})
    assert events.pending_age(0,6.)==6.
    assert events.pending_age(1,6.)==2.
    assert events.pending_age(2,100.)==0.

def test_new_task_drops_previous_task_pending_times(monkeypatch):
    events,clock=event_stream(monkeypatch)
    events.emit('old_task',{});events.begin('second');clock[0]=100.
    events.emit('new_task',{})
    assert events.seq==1 and events.run_id=='second'
    assert events.pending_age(0,100.)==0.
