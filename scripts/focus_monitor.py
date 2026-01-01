import time
import uiautomation as auto
from datetime import datetime

log_file = 'focus_events.txt'
print(f'포커스 이벤트 -> {log_file} (Ctrl+C 종료)')

last = ''
with open(log_file, 'w', encoding='utf-8') as f:
    f.write(f'포커스 모니터링 시작: {datetime.now()}\n')
    f.write('-' * 60 + '\n')
    while True:
        try:
            ctrl = auto.GetFocusedControl()
            if ctrl and ctrl.Name != last:
                ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                line = f'[{ts}] {ctrl.ControlTypeName}: {ctrl.Name}'
                print(line)
                f.write(line + '\n')
                f.flush()
                last = ctrl.Name
        except: pass
        time.sleep(0.05)
