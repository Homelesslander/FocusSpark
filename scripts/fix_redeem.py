from pathlib import Path
p = Path(r'c:\Users\aidie\ADHD-Software-Project\templates\redeem.html')
s = p.read_text(encoding='utf-8')
marker = '<!-- load celebration helpers so we can show confetti on expiry modal -->'
if marker in s:
    # clean JS to replace the broken block
    new_script = '''<!-- load celebration helpers so we can show confetti on expiry modal -->
<script src="{{ url_for('static', filename='celebration.js') }}"></script>
<script>
// Countdown timers for redeemed rewards. When a timer reaches zero, show a friendly modal and remove the item after user clicks OK.
function startRedeemedTimers(){
  const items = document.querySelectorAll('#redeemedList .redeemed-item');
  items.forEach(item => {
    const iso = item.getAttribute('data-expires-at');
    if(!iso) return; // permanent or missing

    // prefer an explicit .countdown element, otherwise find a strong inside redeemed-time
    let countdownElStrong = item.querySelector('.countdown');
    if(!countdownElStrong){
      const rt = item.querySelector('.redeemed-time');
      if(rt) countdownElStrong = rt.querySelector('strong');
    }

    let interval = null;

    function showExpiryModal(title, message, onClose){
      const overlay = document.createElement('div');
      overlay.style.position = 'fixed';
      overlay.style.left = '0';
      overlay.style.top = '0';
      overlay.style.width = '100%';
      overlay.style.height = '100%';
      overlay.style.background = 'rgba(0,0,0,0.5)';
      overlay.style.display = 'flex';
      overlay.style.alignItems = 'center';
      overlay.style.justifyContent = 'center';
      overlay.style.zIndex = '10000';

      const box = document.createElement('div');
      box.style.background = '#fff';
      box.style.borderRadius = '14px';
      box.style.padding = '18px';
      box.style.maxWidth = '460px';
      box.style.width = '88%';
      box.style.boxShadow = '0 12px 36px rgba(0,0,0,0.25)';
      box.style.textAlign = 'center';

      const h = document.createElement('h2');
      h.innerText = title;
      h.style.margin = '0 0 8px 0';
      h.style.fontSize = '20px';

      const p = document.createElement('p');
      p.innerText = message;
      p.style.margin = '0 0 16px 0';
      p.style.fontSize = '15px';

      const ok = document.createElement('button');
      ok.innerText = 'OK';
      ok.style.background = '#ff8c42';
      ok.style.color = '#fff';
      ok.style.border = 'none';
      ok.style.padding = '10px 18px';
      ok.style.borderRadius = '10px';
      ok.style.cursor = 'pointer';
      ok.style.fontSize = '16px';

      ok.addEventListener('click', () => {
        if (overlay.parentElement) overlay.parentElement.removeChild(overlay);
        if (typeof onClose === 'function') onClose();
      });

      box.appendChild(h);
      box.appendChild(p);
      box.appendChild(ok);
      overlay.appendChild(box);
      document.body.appendChild(overlay);
    }

    function parseExpiry(s){
      if(!s) return null;
      // Try direct parse
      let d = new Date(s);
      if(!isNaN(d.getTime())) return d;
      // Replace space with T and try
      d = new Date(s.replace(' ', 'T'));
      if(!isNaN(d.getTime())) return d;
      // Truncate microseconds (more than 3 digits) to milliseconds
      let truncated = s.replace(/\.(\d{3})\d+/, '.$1');
      d = new Date(truncated);
      if(!isNaN(d.getTime())) return d;
      // Append Z (UTC) fallback
      d = new Date(s.replace(' ', 'T') + 'Z');
      if(!isNaN(d.getTime())) return d;
      return null;
    }

    function tick(){
      try{
        const exp = parseExpiry(iso);
        if (!exp) {
          if (countdownElStrong) countdownElStrong.innerText = 'Permanent';
          if (interval) clearInterval(interval);
          return;
        }
        const now = new Date();
        const diff = exp - now;
        if(diff <= 0){
          try{ if (typeof createConfetti === 'function') createConfetti(); }catch(e){}
          showExpiryModal('🎉 Time’s Up!', 'Your reward "' + (item.querySelector('.redeemed-title').innerText) + '" has ended. Click OK to close.', function(){
            if (item.parentElement) item.parentElement.removeChild(item);
            if (interval) clearInterval(interval);
          });
          return;
        }
        const mins = Math.floor(diff/60000);
        const secs = Math.floor((diff%60000)/1000);
        if (countdownElStrong) countdownElStrong.innerText = mins + ':' + String(secs).padStart(2,'0');
      }catch(e){
        console.debug('redeemed timer parse error for', iso, e);
      }
    }

    // start ticking
    tick();
    interval = setInterval(tick, 1000);
  });
}

document.addEventListener('DOMContentLoaded', startRedeemedTimers);
if (document.readyState === 'interactive' || document.readyState === 'complete') {
  startRedeemedTimers();
}
</script>
</html>
'''
    # build new content: keep everything before marker, include marker and new script
    before, _ = s.split(marker, 1)
    new_content = before + marker + '\n' + new_script
    p.write_text(new_content, encoding='utf-8')
    print('patched')
else:
    print('marker not found')
