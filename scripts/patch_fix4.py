from pathlib import Path
root = Path(r'c:\Users\aidie\ADHD-Software-Project')

# 1) update celebration durations by simple replace
cfile = root / 'static' / 'celebration.js'
s = cfile.read_text(encoding='utf-8')
s2 = s.replace('Major: 3000', 'Major: 5000').replace('Medium: 3000', 'Medium: 5000').replace('Minor: 3000', 'Minor: 5000')
if s2 != s:
    cfile.write_text(s2, encoding='utf-8')
    print('updated celebration durations (simple replace)')
else:
    print('no duration pattern found to replace')

# 2) insert a guard before showExpiryModal call in redeem.html
rfile = root / 'templates' / 'redeem.html'
s = rfile.read_text(encoding='utf-8')
search = "showExpiryModal('🎉 Time’s Up!'"
if search in s:
    insert = "if (item.__expiryShown) return; item.__expiryShown = true; if (interval) { clearInterval(interval); interval = null; } "
    s2 = s.replace(search, insert + search)
    rfile.write_text(s2, encoding='utf-8')
    print('inserted expiry guard in redeem.html')
else:
    print('expiry modal call not found in redeem.html')
