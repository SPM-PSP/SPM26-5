<<<<<<< HEAD
from __future__ import annotations

import sys
from pathlib import Path
=======
from pathlib import Path
import sys
>>>>>>> 549c716 (Finish the basic code framework)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
<<<<<<< HEAD
    sys.path.insert(0, str(PROJECT_ROOT))
=======
    sys.path.insert(0, str(PROJECT_ROOT))
>>>>>>> 549c716 (Finish the basic code framework)
