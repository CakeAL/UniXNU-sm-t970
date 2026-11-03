#!/usr/bin/env python3
"""Exercise the actual prepared EDGE QoS-width function with topology mocks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
text = a.source.read_text()
start = text.rindex('uint32_t\nsched_edge_qos_max_parallelism(')
end = text.index('\n}', start) + 2
actual = text[start:end]
assert 'smp_count' in actual
prelude = r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#define CLUSTER_TYPE_SMP 0
#define CLUSTER_TYPE_E 1
#define CLUSTER_TYPE_P 2
#define QOS_PARALLELISM_COUNT_LOGICAL 1
#define QOS_PARALLELISM_REALTIME 2
#define QOS_PARALLELISM_CLUSTER_SHARED_RESOURCE 4
#define THREAD_QOS_MAINTENANCE 1
#define THREAD_QOS_BACKGROUND 2
#define THREAD_QOS_UTILITY 3
static uint32_t cpus[3],clusters[3];
static uint32_t ml_get_cpu_number_type(unsigned type,bool logical,bool available){assert(!logical&&!available&&type<3);return cpus[type];}
static uint32_t ml_get_cluster_number_type(unsigned type){assert(type<3);return clusters[type];}
'''
main = r'''
int main(void){
 for(unsigned qos=1;qos<=7;qos++)for(unsigned opt=0;opt<8;opt++){
  cpus[0]=8;cpus[1]=cpus[2]=0;clusters[0]=1;clusters[1]=clusters[2]=0;
#ifdef BCM2837
  assert(sched_edge_qos_max_parallelism(qos,opt)==((opt&4)?1:8));
  cpus[0]=1;assert(sched_edge_qos_max_parallelism(qos,opt)==1);
#else
  assert(sched_edge_qos_max_parallelism(qos,opt)==0);
#endif
  /* Existing E/P policy must prevail even with an extra SMP entry. */
  cpus[0]=8;cpus[1]=4;cpus[2]=4;clusters[0]=1;clusters[1]=1;clusters[2]=2;
  unsigned expected=(opt&2)?((opt&4)?2:4):(qos<=2?((opt&4)?1:4):((opt&4)?3:8));
  assert(sched_edge_qos_max_parallelism(qos,opt)==expected);
  cpus[0]=cpus[1]=cpus[2]=0;clusters[0]=clusters[1]=clusters[2]=0;
  assert(sched_edge_qos_max_parallelism(qos,opt)==0);
 }
 return 0;
}
'''
a.output.mkdir(parents=True, exist_ok=False)
source = a.output / 'test.c'
source.write_text(prelude + actual + main)
for define in (True, False):
    exe = a.output / ('test-bcm' if define else 'test-other')
    command = ['xcrun', 'clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined']
    if define:
        command += ['-DBCM2837=1']
    subprocess.run(command + [str(source), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
(a.output / 'report.json').write_text(json.dumps(dict(
    source_function_sha256=hashlib.sha256(actual.encode()).hexdigest(),
    actual_prepared_function=True, topology_apis_mocked=True,
    smp_one_and_eight=True, unchanged_ep_policy=True, non_bcm_unchanged=True,
    qos_options_combinations_per_target=56, asan_ubsan=True,
    device_result_pending=True), indent=2) + '\n')
print('PASS: actual EDGE width, SMP1/8, E/P precedence, QoS/options and non-BCM guard')
