import urllib.request
import urllib.parse
import json
from pathlib import Path

def upload_file(url, file_path, workspace_id='satquery_portblair_test'):
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body = []
    
    # workspace_id form field
    body.append(f'--{boundary}'.encode('utf-8'))
    body.append(b'Content-Disposition: form-data; name="workspace_id"')
    body.append(b'')
    body.append(workspace_id.encode('utf-8'))
    
    # file form field
    mime_type = 'image/tiff'
    body.append(f'--{boundary}'.encode('utf-8'))
    body.append(f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"'.encode('utf-8'))
    body.append(f'Content-Type: {mime_type}'.encode('utf-8'))
    body.append(b'')
    with open(file_path, 'rb') as f:
        body.append(f.read())
        
    body.append(f'--{boundary}--'.encode('utf-8'))
    body.append(b'')
    
    content = b'\r\n'.join(body)
    req = urllib.request.Request(
        url,
        data=content,
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Content-Length': str(len(content))
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def main():
    sar_dir = Path(r'D:\SIH PROJECT\SATELLITE IMG\port blair\SEN1A_SAR_IW_13APR2026_064061_747B_ESA_ST0C00NTD_DV\S1A_IW_GRDH_1SDV_20260413T120120_20260413T120145_064061_080F88_747B.SAFE\measurement')
    vv_file = sar_dir / 's1a-iw-grd-vv-20260413t120120-20260413t120145-064061-080f88-001.tiff'
    vh_file = sar_dir / 's1a-iw-grd-vh-20260413t120120-20260413t120145-064061-080f88-002.tiff'

    print('[Test] Uploading VV to HTTP endpoint /api/images/upload...')
    r_vv = upload_file('http://127.0.0.1:8000/api/images/upload', vv_file)
    print(f'  [OK] VV upload: success={r_vv["success"]}, scene_id={r_vv.get("scene_id")}, band={r_vv.get("band_information", {}).get("band")}')
    print(f'       Preview URL: {r_vv.get("preview", {}).get("preview_url")}')

    print('\n[Test] Uploading VH to HTTP endpoint /api/images/upload...')
    r_vh = upload_file('http://127.0.0.1:8000/api/images/upload', vh_file)
    print(f'  [OK] VH upload: success={r_vh["success"]}, scene_id={r_vh.get("scene_id")}, band={r_vh.get("band_information", {}).get("band")}')
    print(f'       Preview URL: {r_vh.get("preview", {}).get("preview_url")}')

    # Verify both have identical scene_id
    assert r_vv['scene_id'] == r_vh['scene_id'], f"Scene IDs must match! {r_vv['scene_id']} vs {r_vh['scene_id']}"
    print(f'\n  [OK] Both VV and VH assigned identical scene_id: {r_vv["scene_id"]}')

    print('\n[Test] Querying /api/scenes to verify scene unification...')
    req = urllib.request.Request('http://127.0.0.1:8000/api/scenes?workspace_id=satquery_portblair_test')
    with urllib.request.urlopen(req) as resp:
        scenes_data = json.loads(resp.read().decode('utf-8'))['data']

    sar_scenes = [s for s in scenes_data['scenes'] if '20260413' in s['scene_id']]
    print(f'  [OK] Number of SAR scenes for 20260413: {len(sar_scenes)}')
    assert len(sar_scenes) == 1, f"Expected 1 SAR scene, got {len(sar_scenes)}"
    unified_sar = sar_scenes[0]
    print(f'       Scene ID: {unified_sar["scene_id"]}')
    print(f'       Title: {unified_sar["title"]}')
    print(f'       Bands: {unified_sar["bands"]}')
    print(f'       Dual-Pol Available: {unified_sar["available_analyses"]["sar_dual_pol"]}')
    print(f'       Thumbnail URL: {unified_sar["thumbnail_url"]}')
    assert 'VV' in unified_sar['bands'] and 'VH' in unified_sar['bands'], "Both VV and VH must be present in unified scene!"
    assert unified_sar['available_analyses']['sar_dual_pol'] is True, "sar_dual_pol must be True!"

    # Now upload the 4 Landsat files to the same workspace
    opt_dir = Path(r'D:\SIH PROJECT\SATELLITE IMG\port blair\optical image')
    print('\n[Test] Uploading 4 Landsat-9 Port Blair GeoTIFF bands (B2, B3, B4, B5)...')
    for b_file in ['LC91340522026109SGI00_B2.TIF', 'LC91340522026109SGI00_B3.TIF', 'LC91340522026109SGI00_B4.TIF', 'LC91340522026109SGI00_B5.TIF']:
        r_opt = upload_file('http://127.0.0.1:8000/api/images/upload', opt_dir / b_file)
        print(f'  [OK] Uploaded {b_file}: scene_id={r_opt.get("scene_id")}, band={r_opt.get("band_information", {}).get("band")}')

    # Query /api/scenes again
    with urllib.request.urlopen('http://127.0.0.1:8000/api/scenes?workspace_id=satquery_portblair_test') as resp:
        scenes_data_2 = json.loads(resp.read().decode('utf-8'))['data']

    opt_pb = next((s for s in scenes_data_2['scenes'] if s['scene_id'] == 'LC91340522026109SGI00'), None)
    sar_pb = next((s for s in scenes_data_2['scenes'] if s['scene_id'] == unified_sar['scene_id']), None)
    assert opt_pb is not None, "Optical Landsat scene must be present!"
    assert sar_pb is not None, "SAR Sentinel-1 scene must be present!"
    print(f'\n  [OK] Optical Scene: {opt_pb["scene_id"]} with bands {opt_pb["bands"]}')
    print(f'  [OK] SAR Scene: {sar_pb["scene_id"]} with bands {sar_pb["bands"]}')

    # Now execute optical + SAR fusion query via /api/query!
    print('\n[Test] Executing Optical + SAR Fusion query via /api/query...')
    query_payload = {
        'query': 'Analyze this scene using optical and SAR data.',
        'mode': 'fusion',
        'active_scene_id': opt_pb['scene_id'],
        'optical_scene_id': opt_pb['scene_id'],
        'sar_scene_id': sar_pb['scene_id'],
        'workspace_id': 'satquery_portblair_test'
    }
    query_req = urllib.request.Request(
        'http://127.0.0.1:8000/api/query',
        data=json.dumps(query_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(query_req) as resp:
        q_res = json.loads(resp.read().decode('utf-8'))

    print(f'  [OK] Query Result: success={q_res.get("success")}, selected_tool={q_res.get("selected_tool")}')
    assert q_res.get('success') is True, f"Query failed: {q_res.get('error')}"
    assert q_res.get('selected_tool') == 'optical_sar_model', f"Expected optical_sar_model, got {q_res.get('selected_tool')}"
    ev = q_res.get('evidence', {}) or q_res.get('analysis', {}).get('evidence', {})
    print(f'  [OK] Fusion Composite generated: {ev.get("fusion_composite")}')
    print(f'  [OK] Mean NDVI: {q_res.get("analysis", {}).get("optical_metrics", {}).get("mean_ndvi")}')
    print(f'  [OK] Cross-Sensor Agreement: {q_res.get("analysis", {}).get("fusion_metrics", {}).get("cross_sensor_vegetation_agreement_pct")}%')

    print('\n' + '=' * 70)
    print('ALL HTTP ENDPOINTS & WORKSPACE FLOW VERIFIED SUCCESSFULLY!')
    print('=' * 70)

if __name__ == '__main__':
    main()
