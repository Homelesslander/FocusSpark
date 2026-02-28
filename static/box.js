document.addEventListener('DOMContentLoaded', function(){
  const toggle = document.getElementById('box-toggle');
  const contents = document.getElementById('box-contents');
  const itemsEl = document.getElementById('box-items');
  const countEl = document.getElementById('box-count');
  const boxSvg = document.querySelector('.box-svg');

  async function refreshBoxItems(){
    try{
      const res = await fetch('/box/items');
      if(!res.ok) throw new Error('Failed');
      const items = await res.json();
      countEl.textContent = items.length;
      if(items.length === 0){
        itemsEl.innerHTML = '<div style="padding:8px;color:#333">No items in your box yet.</div>';
        return;
      }
      itemsEl.innerHTML = '';
      items.forEach(it => {
        const div = document.createElement('div');
        div.className = 'box-item';
        const meta = document.createElement('div'); meta.className = 'meta';
        const title = document.createElement('div'); title.className = 'title'; title.textContent = it.name;
        const sub = document.createElement('div'); sub.className = 'sub'; sub.textContent = it.date ? ('Due: ' + it.date) : 'No date';
        meta.appendChild(title); meta.appendChild(sub);

        const actions = document.createElement('div'); actions.className = 'actions';
        const restore = document.createElement('button'); restore.className = 'restore'; restore.textContent = 'Restore';
        restore.addEventListener('click', async function(e){
          e.preventDefault();
          restore.disabled = true;
          try{
            const r = await fetch('/box/remove/' + it.id, {method:'POST'});
            if(r.ok){
              await refreshBoxItems();
              // optimistic page refresh to update lists
              window.location.reload();
            } else {
              restore.disabled = false;
            }
          } catch(err){
            console.error(err); restore.disabled = false;
          }
        });
        actions.appendChild(restore);

        div.appendChild(meta); div.appendChild(actions);
        itemsEl.appendChild(div);
      });
    }catch(e){
      itemsEl.innerHTML = '<div style="padding:8px;color:#900">Could not load box items</div>';
      console.error(e);
    }
  }

  toggle.addEventListener('click', function(){
    const open = toggle.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if(open){
      contents.hidden = false;
      // show lid open
      if(boxSvg) boxSvg.classList.add('lid-open');
      refreshBoxItems();
    } else {
      contents.hidden = true;
      if(boxSvg) boxSvg.classList.remove('lid-open');
    }
  });

  // initial load to show count
  (async function(){
    try{
      const res = await fetch('/box/items');
      const items = res.ok ? await res.json() : [];
      countEl.textContent = items.length;
    }catch(e){console.error(e)}
  })();

  // Intercept "Put in Box" buttons (class: box-btn) to animate
  document.querySelectorAll('.box-btn').forEach(btn => {
    btn.addEventListener('click', async function(e){
      e.preventDefault();
      const li = btn.closest('li');
      // find task id from dataset or form action
      let taskId = btn.datasetTaskId || btn.getAttribute('data-task-id');
      // fallback: parse from form action if present
      if(!taskId){
        const form = btn.closest('form');
        if(form){
          const action = form.getAttribute('action') || '';
          const m = action.match(/\/box\/add\/(\d+)/);
          if(m) taskId = m[1];
        }
      }
      if(!taskId) return;
      btn.disabled = true;
      try{
        // open lid briefly and pulse
        if(boxSvg) boxSvg.classList.add('lid-open');
        toggle.classList.add('pulse');
        const r = await fetch('/box/add/' + taskId, {method:'POST'});
        if(r.ok){
          // remove task visually with fade
          if(li){
            li.style.transition = 'opacity .35s ease, transform .35s ease';
            li.style.opacity = '0'; li.style.transform = 'translateY(-12px) scale(.98)';
            setTimeout(()=>{ li.remove(); }, 380);
          }
          // update count and box contents if open
          const fresh = await fetch('/box/items');
          const items = fresh.ok ? await fresh.json() : [];
          countEl.textContent = items.length;
          if(toggle.classList.contains('open')){
            await refreshBoxItems();
          }
        } else {
          console.error('Add to box failed');
        }
      } catch(err){
        console.error(err);
      } finally{
        btn.disabled = false;
        // close lid after short delay
        setTimeout(()=>{ if(boxSvg) boxSvg.classList.remove('lid-open'); toggle.classList.remove('pulse'); }, 650);
      }
    });
  });
});
