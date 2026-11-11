const inventory = document.querySelector('#inventory');
const feedback = document.querySelector('#feedback');

async function refresh() {
  const response = await fetch('/v1/systems');
  if (!response.ok) throw new Error('Failed to load inventory');
  const systems = await response.json();
  inventory.replaceChildren();
  if (!systems.length) { inventory.textContent = 'No systems registered.'; return; }
  for (const system of systems) {
    const card = document.createElement('article');
    const title = document.createElement('strong');
    title.textContent = system.name;
    const detail = document.createElement('p');
    detail.textContent = `${system.impact} impact · Owner: ${system.owner} · Revision ${system.revision}`;
    const link = document.createElement('a');
    link.href = `/v1/systems/${encodeURIComponent(system.id)}`;
    link.textContent = 'View system record';
    card.append(title, detail, link);
    inventory.append(card);
  }
}

document.querySelector('#register').addEventListener('submit', async event => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const response = await fetch('/v1/systems', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(JSON.stringify(result.detail));
    feedback.textContent = `Registered ${result.name}`;
    await refresh();
  } catch (error) { feedback.textContent = error.message; }
});

document.querySelector('#refresh').addEventListener('click', () => {
  refresh().catch(error => { inventory.textContent = error.message; });
});
refresh().catch(error => { inventory.textContent = error.message; });
