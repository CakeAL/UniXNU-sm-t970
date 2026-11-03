"""Exercise the actual diagnostic counter/formatter block under ASan."""
from pathlib import Path
import subprocess
import tempfile
import unittest

class State(unittest.TestCase):
    def test_counter_snapshot_and_bounds(self):
        source=(Path(__file__).resolve().parents[1]/'package/T970Display/DisplayRegistration.cpp').read_text()
        block=source[source.index('static volatile unsigned displayStage'):source.index('static bool consoleReleased')]
        code='#include <cstdint>\n#include <cstdio>\n#include <cstring>\n#include <cassert>\n'+block+r'''
int main() {
    displayStage=8; displayMeta=0; displaySurface=0; displayMapped=displayPublished=1;
    for (unsigned i=0;i<100;++i) note(clientsEntered);
    note(clientsOpened); note(clientsFailed); note(swapsAccepted); note(swapsRejected);
    note(transfers); note(copies); note(retired); note(vsyncSent);
    lastClientType=2; lastClientStatus=0xe00002c7; lastTransferStatus=0;
    for(unsigned n : {0u,1u,16u,384u}) {
        char bytes[386]; memset(bytes,'Z',sizeof(bytes));
        native_t970_display_state(bytes+1,n);
        assert(bytes[0]=='Z' && bytes[n+1]=='Z');
        if(n) assert(memchr(bytes+1,0,n));
        assert(sample(clientsEntered)==100 && sample(clientsOpened)==1);
    }
    char text[384]; native_t970_display_state(text,sizeof(text));
    assert(strstr(text,"display stage=8"));
    assert(strstr(text,"enter/open/fail=100/1/1"));
    assert(strstr(text,"swap ok/bad=1/1"));
    assert(strstr(text,"copies=1 retire=1 vsync=1"));
    native_t970_display_state(nullptr,20);
}
'''
        code='#include <initializer_list>\n'+code
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'state.cpp';exe=Path(d)/'state';src.write_text(code)
            subprocess.run(['xcrun','clang++','-std=c++17','-fsanitize=address','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
