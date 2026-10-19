from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parent.parent
old=R/'.reference/hd-lateTerrain7-SourceF-fixedH5567-genuine29-context-20261018-v1'
s=(old/'compose_LateTerrain7_genuine29_SourceF_H5567.rs').read_text()
s=s.replace('//! LateTerrain7 / immutableN15 H5567:29 genuine endpoints,18 ordered views,14 events; World0. All seven have genuine callers. Two semantic-retention frames use plain prejoin and exact six Original cells after joins.','//! Grating2 / immutableH5613 currentG2:12 actual static callers plus2 genuine foreign-neighbor states;14 endpoints/2 ordered views. Own health0 remains intact, World0/newQA0/newart0.')
s=s.replace('ROOT_ACTIVATED_SOURCEF_LATE7_GENUINE29_H5567','ROOT_ACTIVATED_SOURCEG2_GRATING2_GENUINE14_H5613').replace('Root_actual_H5567_GO','Root_actual_H5613_GO').replace('baseline_assembly_receipt','baseline_hardlink_identity').replace('["3050d","3050f","30510","30511","30513","30519","3051c"]','["203c6","203c7"]').replace('[0x3050d,0x3050f,0x30510,0x30511,0x30513,0x30519,0x3051c]','[0x203c6,0x203c7]')
s=s.replace('5567','5613').replace('H5567','H5613').replace('source_assets.len(),57','source_assets.len(),55').replace('active_own.len(),7','active_own.len(),2').replace('proposal.registered_count(),7','proposal.registered_count(),2').replace('measured.len(),7','measured.len(),2')
lines=s.splitlines()
for i,line in enumerate(lines):
 if line.startswith(' let own_manifest='):
  lines[i]=line.replace('len(),7','len(),2')
 if line.startswith(' for route in contract['):
  a=line.index('assert_eq!(f["atlas_grid"]');b=line.index('assert_eq!(f["frame"],0)',a)
  line=line[:a]+line[b:];line=line.replace('"palette_constraint","native_nearest_cues","preserve_reserved_coverage","crop"','"palette_constraint","native_nearest_cues","preserve_reserved_coverage","crop","atlas_grid","original_detail_cells"');lines[i]=line
 if 'if own.contains(&asset){assert!(domain.is_none());let expected=match asset' in line:
  a=line.index('let expected=match asset');b=line.index('assert_eq!(image.pixels,bank_indices',a)
  line=line[:a]+'assert!(retained.is_none());'+line[b:]
  line=line.replace('Public terrain PRE-retention API image equals actual unretained plain F7 row. Six semantic lavender cells are restored by compositor AFTER joins against joined OriginalNx.','Public terrain prejoin API image equals the literal actual derived G2 native bank; own frames have no retention metadata.').replace('Originaldetails_match_exact_semantic_features','no_Original_functional_retention_selected')
  lines[i]=line
s='\n'.join(lines)+'\n'
s=s.replace('rows.len(),29','rows.len(),14').replace('pairs.len(),18','pairs.len(),2').replace('row_index<29','row_index<14').replace('a<29&&b<29','a<14&&b<14').replace('.len(),14);\n for(index,pair)','.len(),2);\n for(index,pair)')
s=s.replace('if row["role"]=="authentic_intact"{count==0&&actors.is_empty()}else{(1..=2).contains(&count)&&!actors.is_empty()}','if row["role"]=="authentic_static_intact"{count>=1&&actors.is_empty()}else{count>=1&&actors.len()==1}')
s=s.replace('records.len(),116','records.len(),56').replace('"actual_H5613_baseline"','"actual_H5613_baseline"').replace('selected_LateTerrain7_proposal','selected_derived_grating2_proposal').replace('new_genuine_Source_primary7_atlas_route','actual_derived_graycast2_native_route')
s=s.replace('ACTUAL-SOURCEF-LATE7-GENUINE29-116-SCALES-348-PLANES-18VIEWS-14EVENTS.json','ACTUAL-SOURCEG2-GRATING2-GENUINE14-56-SCALES-168-PLANES-2VIEWS-2EVENTS.json').replace('SourceF_domain_aware_public_API','SourceG2_domain_aware_public_API').replace('"genuine_Source_endpoints":29','"genuine_Source_endpoints":14').replace('"ordered_comparisons":18','"ordered_comparisons":2').replace('"distinct_damage_events":14','"distinct_damage_events":2').replace('own_used7_prejoin_exact_actual_F7_rows','own_used2_prejoin_exact_actual_derived_G2_rows').replace('representative11_own_states_plus4_mutual_views_and3_other_neighbor_views','all12_static_callers_plus2_genuine_foreign_neighbor_events').replace('all_endpoints_fresh_immutable_H5613_no_old_context_output_carry','all_endpoints_fresh_immutable_H5613_no_old_context_output_carry')
s=s.replace('ACTUAL SourceF late7 genuine29;116scales348planes18views14events; selected7allUsed; compile1 constructor1 World0 QA0','ACTUAL SourceG2 grating2 genuine14;56scales168planes2views2events; selected2allUsed; compile1 constructor1 World0 QA0')
assert '3050'not in s and '3051'not in s and '5567'not in s and '29)'not in s
# Original adapter generation preserved in history; do not run this prep again after actual execution.
assert not (O/'ACTUAL-ONE-COMPILE-STARTED.json').exists(), 'Do not regenerate after actual compile'
(O/'compose_Grating2_genuine14_SourceG2_H5613.rs').write_text(s)
a=(old/'authenticate_saved_Late7_context_and_present.py').read_text()
a=a.replace("O=F/'actual-context29'","O=F/'actual-context14'").replace('ACTUAL-SOURCEF-LATE7-GENUINE29-116-SCALES-348-PLANES-18VIEWS-14EVENTS.json','ACTUAL-SOURCEG2-GRATING2-GENUINE14-56-SCALES-168-PLANES-2VIEWS-2EVENTS.json')
a=a.replace("(W/'data/misc/PALETTE_DAT')","(R/'data/misc/PALETTE_DAT')")
a=a.replace("len(x['records'])==116 and len(x['components'])==212 and len(x['ordered_pairs'])==18","len(x['records'])==56 and len(x['components'])==220 and len(x['ordered_pairs'])==2")
a=a.replace('len(sources)==57','len(sources)==55').replace('len(bank)==28','len(bank)==8').replace('actual_H5567_baseline','actual_H5613_baseline').replace('selected_LateTerrain7_proposal','selected_derived_grating2_proposal')
a=a.replace('assert (sum(v in own for v in ids)==0 if e["role"]=="authentic_intact"else 1<=sum(v in own for v in ids)<=2)','assert sum(v in own for v in ids)>=1;assert (len(e["settled_actors"])==0 if e["role"]=="authentic_static_intact"else len(e["settled_actors"])==1)')
a=a.replace('len(rows)==29 and len(pairauth)==18 and len({p[\'event_id\']for p in pairauth})==14','len(rows)==14 and len(pairauth)==2 and len({p[\'event_id\']for p in pairauth})==2')
a=a.replace('SourceF cfabd / actualH5567 | whole3x3 native1-4 | 29 finite genuine / 18 ordered views / 14 real events','SourceG2 5b6 / actualH5613 | whole3x3 native1-4 | all12 callers +2 foreign-neighbor states')
a=a.replace('Actual5567 baseline','Actual5613 baseline').replace('New lateTerrain7 proposal','Derived grating2 proposal')
a=a.replace('FILE-ONLY-LATE7-29-ENDPOINTS-348-PLANES-212-COMPONENTS-AUTHENTICATION.json','FILE-ONLY-GRATING2-14-ENDPOINTS-168-PLANES-220-COMPONENTS-AUTHENTICATION.json').replace('COMPLETE29-GENUINE-348-NATIVE-PANES-EIGHTEEN-ORDERED-VIEWS-PAGE-ARRAY-INTERFACE.json','COMPLETE14-GENUINE-168-NATIVE-PANES-TWO-ORDERED-VIEWS-PAGE-ARRAY-INTERFACE.json')
a=a.replace('actual_own_pre_components=28','actual_own_pre_components=8').replace('own_prejoin_matches_exact_existing_plain_SourceF_F7_used7_rows=True','own_prejoin_matches_exact_literal_actual_derived_G2_bank=True').replace('own_Originaldetails_exact_six_semantic_lavender_cells=True','own_Originaldetails_absent=True')
a=a.replace('unique_whole_endpoint_pane_bodies=348','unique_whole_endpoint_pane_bodies=168').replace('ordered_pair_duplicate_panes=432','ordered_pair_duplicate_panes=48').replace('page_readbacks=780','page_readbacks=216')
a=a.replace('unique_Original_Source_endpoints=29','unique_Original_Source_endpoints=14').replace('unique_scale_records=116','unique_scale_records=56').replace('unique_native_whole_planes=348','unique_native_whole_planes=168').replace('endpoint_whole_pages=29','endpoint_whole_pages=14').replace('ordered_pair_whole_pages=18','ordered_pair_whole_pages=2').replace('ordered_pair_panes_duplicate_endpoints=432','ordered_pair_panes_duplicate_endpoints=48').replace('whole_native_page_count=47','whole_native_page_count=16').replace('actual_H5567','actual_H5613').replace('SourceF_epoch','SourceG2_epoch')
a=a.replace('prejoin_matches_actual_SourceF_F7_selected_row','prejoin_matches_literal_actual_derived_G2_selected_row').replace('genuine_Source_primary7_atlas_row','actual_derived_grating2_row')
start=a.index("static_ordered_pair_semantics='");end=a.index("'))",start)
a=a[:start]+"static_ordered_pair_semantics='All12 actual static callers plus2 controlled legal foreign-neighbor states, exactly2 distinct one-cell events. Own grating health0/reward0 has no settled state. Full genuine Registry/FLATS matches, no World/natural timing claim. Exact public prejoin own pixels equal literalG2QA62d093c4 bank, selected no retention. Foreign complete frame metadata and Original details/domains preserved. Immutable5613 baseline b13a4f7c, actualG2 library5b6; no historical capture or newintrinsic claim."+a[end:]
a=a.replace('all_SourceNx_class_palette_domain_alpha_PPMS_reserved_outside_foreign_fallback_padding_role_checks_exact','all_SourceNx_class_palette_domain_PPMS_reserved_outside_foreign_fallback_padding_role_checks_exact')
assert '5567'not in a and '==29'not in a and '348'not in a and 'SourceF'not in a
(O/'authenticate_saved_Grating2_context_and_present.py').write_text(a)
