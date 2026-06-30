# Auto-generated OpenROAD Partition Manager / TritonPart demo
set num_parts 4
set balance_constraint 2
set seed 7
set hypergraph_file "classic_results/openroad_tritonpart/demo_top.hgr"
set solution_file "classic_results/openroad_tritonpart/demo_top.hgr.part.4"
triton_part_hypergraph -hypergraph_file $hypergraph_file \
  -num_parts $num_parts -balance_constraint $balance_constraint \
  -seed $seed
evaluate_hypergraph_solution -num_parts $num_parts \
  -balance_constraint $balance_constraint \
  -hypergraph_file $hypergraph_file -solution_file $solution_file
