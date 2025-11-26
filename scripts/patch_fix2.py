from pathlib import Path
root = Path(r'c:\Users\aidie\ADHD-Software-Project')
# 1) update celebration durations
cfile = root / 'static' / 'celebration.js'
s = cfile.read_text(encoding='utf-8')
old = "const DISPLAY_DURATIONS = {\n    Major: 3000,\n    Medium: 3000,\n    Minor: 3000\n  };"
new = "const DISPLAY_DURATIONS = {\n    Major: 5000,\n    Medium: 5000,\n    Minor: 5000\n  };"
if old in s:
    s = s.replace(old, new)
    cfile.write_text(s, encoding='utf-8')
    print('updated celebration durations')
else:
    print('duration block not found; skipping')

# 2) update redeem.html tick expiry handling
rfile = root / 'templates' / 'redeem.html'
s = rfile.read_text(encoding='utf-8')
old_segment = "if(diff <= 0){\n          try{ if (typeof createConfetti === 'function') createConfetti(); }catch(e){}\n          showExpiryModal('🎉 Time’s Up!', 'Your reward "' + (item.querySelector('.redeemed-title').innerText) + '" has ended. Click OK to close.', function(){\n            if (item.parentElement) item.parentElement.removeChild(item);\n            if (interval) clearInterval(interval);\n          });\n          return;\n        }"
new_segment = "if(diff <= 0){\n          if (item.__expiryShown) return;\n          item.__expiryShown = true;\n          try{ if (typeof createConfetti === 'function') createConfetti(); }catch(e){}\n          if (interval) { clearInterval(interval); interval = null; }\n          showExpiryModal('🎉 Time’s Up!', 'Your reward \"' + (item.querySelector('.redeemed-title').innerText) + '\" has ended. Click OK to close.', function(){\n            if (item.parentElement) item.parentElement.removeChild(item);\n          });\n          return;\n        }"
if old_segment in s:
    s = s.replace(old_segment, new_segment)
    rfile.write_text(s, encoding='utf-8')
    print('patched redeem tick expiry handling')
else:
    print('expected tick segment not found; attempting relaxed replace')
    # fallback: try to replace a smaller pattern
    if "showExpiryModal('🎉 Time’s Up!" in s:
        s = s.replace("showExpiryModal('🎉 Time’s Up!',", "if (item.__expiryShown) return; item.__expiryShown = true; if (interval) { clearInterval(interval); interval = null; } showExpiryModal('🎉 Time’s Up!',")
        rfile.write_text(s, encoding='utf-8')
        print('applied relaxed patch')
    else:
        print('could not find expiry show call; manual edit required')
