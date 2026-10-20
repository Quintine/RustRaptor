from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parent.parent
p=O/'compose_Quiet9_genuine16_SourceG2_H5647.rs';s=p.read_text().replace('actual_selected_plain_index_banks','actual_selected_POST_retention_index_banks').replace(',"unused_disallowed_metadata"','');p.write_text(s)
s=(R/'.reference/hd-grating2-SourceG2-H5613-genuine14-context-20261019-v1/execute_grating2_context_once.py').read_text()
s=s.replace('GRATING2','QUIET9').replace('grating2','quiet9').replace('Grating2','Quiet9').replace('H5613','H5647').replace('5613','5647').replace('GENUINE14','GENUINE_CONTEXT').replace('genuine14','genuine16').replace('actual-context14','actual-context16').replace('FROZEN-QUIET9-G2-H5647-GENUINE_CONTEXT-SOURCE-CONTRACT.json','FROZEN-QUIET9-G2-LITERAL-BASELINE-GENUINE-SOURCE-CONTRACT.json').replace('120000000','150000000').replace('2_200_000_000','1_800_000_000').replace('actual_selected_plain_index_banks','actual_selected_POST_retention_index_banks').replace("q['actual_plain_bank']","q['actual_bank']")
assert 'plain'not in s;assert 'grating'not in s.lower();assert '5636'not in s
(O/'execute_quiet9_context_once.py').write_text(s)
