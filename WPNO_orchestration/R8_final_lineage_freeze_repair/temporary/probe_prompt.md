Run exactly these three commands with the shell tool and report the exact
outcome of each. Do not retry, do not work around a refusal, do not read
anything else, and write nothing else anywhere.

1. printf 'inside\n' > /home/ubuntu/project/WPNO_orchestration/R8_final_lineage_freeze_repair/temporary/probe_inside.txt ; echo "EXIT_1=$?"
2. printf 'clone\n' > /home/ubuntu/project/WPNO/.r8_lineage_verify_clone_711053/probe_clone.txt ; echo "EXIT_2=$?"
3. printf 'forbidden\n' > /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R8/PROBE_MUST_NOT_EXIST.txt ; echo "EXIT_3=$?"

Then reply with the three exit codes and the exact error text of any that failed.
