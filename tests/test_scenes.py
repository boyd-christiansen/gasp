"""Scene provenance and resumable-session state, using only a simulator."""
import pytest
from fastapi.testclient import TestClient
from gasp.server import create_app
from gasp.storage import atomic_json


def test_scene_snapshot_and_session_progress(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        assert c.post('/api/scenes', json={'name':'  ', 'subject':'Boyd'}).status_code == 400
        scene = c.post('/api/scenes', json={'name':'Desk', 'subject':'Tester', 'location':'Lab',
            'distance_cm':45, 'enclosure':'Bare board', 'yaw_deg':0}).json()
        assert c.get('/api/scenes').json() == [scene]
        c.post('/api/connect', json={'source':'simulator'})
        request = {'name':'First session', 'subject':'Tester', 'collection':{
            'scene_id':scene['id'],'deck_id':'commands-v1','mode':'voiced',
            'distance_cm':99,'location':'client must not override saved placement'}}
        first = c.post('/api/sessions', json=request).json()
        assert first['collection']['distance_cm'] == 45
        assert first['collection']['location'] == 'Lab'
        assert first['collection']['scene_snapshot'] == scene
        assert first['collection']['scene_name'] == 'Desk'
        second = c.post('/api/sessions', json=request).json()
        assert first['id'] != second['id']
        assert first['profile']['sha256'] == second['profile']['sha256']
        request['subject']='Other person'
        assert c.post('/api/sessions', json=request).status_code == 400
        request['subject']='Tester'; request['collection']['scene_id']='../../outside'
        assert c.post('/api/sessions', json=request).status_code == 400
        request['collection']['scene_id']='missing'
        assert c.post('/api/sessions', json=request).status_code == 404
        # Duplicate retakes do not inflate progress. Rejected attempts do not count.
        steps=first['collection']['plan']['steps']
        for i,(step,status) in enumerate([(steps[0],'pending'),(steps[0],'verified'),(steps[1],'rejected')]):
            atomic_json(tmp_path/'sessions'/first['id']/'trials'/str(i)/'trial.json',
                {'id':str(i),'plan_step_id':step['step_id'],'review_status':status,
                 'accepted':status=='verified','created_ns':i})
        block=next(s for s in c.get('/api/blocks').json() if s['id']==first['id'])
        assert block['completed_steps']==1 and block['verified_steps']==1
        assert block['step_count']==14 and block['pending_count']==1
        assert 'steps' not in block['collection']['plan']
        # Later scene-file changes cannot rewrite any existing session's conditions.
        atomic_json(tmp_path/'scenes'/(scene['id']+'.json'),dict(scene,distance_cm=60))
        saved=c.get('/api/sessions/'+first['id']).json()
        assert saved['collection']['scene_snapshot']['distance_cm']==45
        c.post('/api/disconnect')
        c.post('/api/connect', json={'source':'simulator','profile':'usb-phase-10hz'})
        result=c.post('/api/sessions/'+first['id']+'/resume')
        assert result.status_code==400 and 'Radar settings' in result.json()['detail']


def test_calibration_cannot_cross_scenes(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        c.post('/api/connect',json={'source':'simulator'})
        a=c.post('/api/scenes',json={'name':'Desk A'}).json()
        b=c.post('/api/scenes',json={'name':'Desk B'}).json()
        calibration=c.post('/api/sessions',json={'name':'Calibration','collection':{
            'scene_id':a['id'],'deck_id':'calibration-v1','visit_role':'calibration'}}).json()
        result=c.post('/api/sessions',json={'name':'Phrases','collection':{
            'scene_id':b['id'],'deck_id':'commands-v1','calibration_id':calibration['id']}})
        assert result.status_code==400 and 'in this setup' in result.json()['detail']


def test_setup_is_saved_as_part_of_starting_collection(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as c:
        request = {'name':'First collection','subject':'Tester',
            'setup':{'name':'Desk','subject':'Tester','location':'Home','distance_cm':50},
            'collection':{'deck_id':'commands-v1','mode':'voiced'}}
        assert c.post('/api/sessions',json=request).status_code == 400
        assert c.get('/api/scenes').json() == []
        c.post('/api/connect',json={'source':'simulator'})
        request['collection']['deck_id']='unknown'
        assert c.post('/api/sessions',json=request).status_code == 400
        assert c.get('/api/scenes').json() == []
        request['collection']['deck_id']='commands-v1'
        result=c.post('/api/sessions',json=request)
        assert result.status_code == 200
        first=result.json()
        scene=c.get('/api/scenes').json()[0]
        assert first['collection']['scene_id'] == scene['id']
        assert first['collection']['scene_snapshot'] == scene
        assert first['collection']['distance_cm'] == 50
        request['collection']['scene_id']=scene['id']
        assert c.post('/api/sessions',json=request).status_code == 400
        del request['setup']
        second=c.post('/api/sessions',json=request).json()
        assert second['id'] != first['id']
        assert second['collection']['scene_snapshot'] == scene
        assert len(c.get('/api/scenes').json()) == 1
