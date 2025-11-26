import re
from pathlib import Path
root = Path(r'c:\Users\aidie\ADHD-Software-Project')

# 1) update celebration durations using regex
cfile = root / 'static' / 'celebration.js'
s = cfile.read_text(encoding='utf-8')
new_s, n = re.subn(r"(DISPLAY_DURATIONS\s*=\s*\{[\s\S]*?Major:\s*)\d+(,\s*Medium:\s*)\d+(,\s*Minor:\s*)\d+(\s*\})",
                   r"\1 5000\2 5000\3 5000\4", s)
if n:
    cfile.write_text(new_s, encoding='utf-8')
    print(f'updated celebration durations ({n} replacements)')
else:
    print('no durations replaced')

# 2) patch redeem.html expiry block
rfile = root / 'templates' / 'redeem.html'
s = rfile.read_text(encoding='utf-8')
pattern = re.compile(r"if\(diff <= 0\)\s*\{[\s\S]*?showExpiryModal\([\s\S]*?\);[\s\S]*?return;\s*\}", re.M)
new_block = ("if(diff <= 0){\n"
             "          if (item.__expiryShown) return;\n"
             "          item.__expiryShown = true;\n"
             "          try{ if (typeof createConfetti === 'function') createConfetti(); }catch(e){}\n"
             "          if (interval) { clearInterval(interval); interval = null; }\n"
             "          showExpiryModal('🎉 Time’s Up!', 'Your reward "' + (item.querySelector('.redeemed-title').innerText) + '\" has ended. Click OK to close.', function(){\n"
             "            if (item.parentElement) item.parentElement.removeChild(item);\n"
             "          });\n"
             "          return;\n"
             "        }")

new_s, n = pattern.subn(new_block, s)
if n:
    rfile.write_text(new_s, encoding='utf-8')
    print(f'patched redeem.html expiry block ({n} replacements)')
else:
    # try more lenient search for showExpiryModal and insert flags
    if "showExpiryModal('🎉 Time’s Up!" in s:
        s = s.replace("showExpiryModal('🎉 Time’s Up!',", "if (item.__expiryShown) return; item.__expiryShown = true; if (interval) { clearInterval(interval); interval = null; } showExpiryModal('🎉 Time’s Up!',")
        rfile.write_text(s, encoding='utf-8')
        print('applied relaxed redeem.html patch')
    else:
        print('could not find expiry modal call in redeem.html')
