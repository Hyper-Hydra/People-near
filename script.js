const API_URL = "http://127.0.0.1:8000";

const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const tgUser = tg?.initDataUnsafe?.user;
const currentUser = {
  id: tgUser?.id || 999999,
  name: tgUser?.first_name || 'Локальный Пользователь',
  username: tgUser?.username ? `@${tgUser.username}` : '@no_username'
};

const screenFeed = document.getElementById('screen-feed');
const screenForm = document.getElementById('screen-form');
const screenProfile = document.getElementById('screen-profile');

const tabFeed = document.getElementById('tab-feed');
const tabForm = document.getElementById('tab-form');
const tabProfile = document.getElementById('tab-profile');

const ordersGrid = document.getElementById('orders-grid');
const searchInput = document.getElementById('search-input');
const emptyState = document.getElementById('empty-state');

const adTitle = document.getElementById('ad-title');
const adDescription = document.getElementById('ad-description');
const adType = document.getElementById('ad-type');
const adPrice = document.getElementById('ad-price');
const priceError = document.getElementById('price-error');
const publishBtn = document.getElementById('publish-btn');

const profileName = document.getElementById('profile-name');
const profileUsername = document.getElementById('profile-username');
const profileRoom = document.getElementById('profile-room');
const userAvatar = document.getElementById('user-avatar');
const saveRoomBtn = document.getElementById('save-room-btn');
const myOrdersList = document.getElementById('my-orders-list');

const detailScreen = document.getElementById('detail-screen');
const detailBack = document.getElementById('detail-back');
const detailContent = document.getElementById('detail-content');
const bottomNav = document.getElementById('bottom-nav');
const toast = document.getElementById('toast');

let orders = [];
let activeCategory = null;
let currentScreen = 'feed';
let detailOrderId = null;
let toastTimer = null;

function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function showToast(message) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.remove('hidden');
  toastTimer = setTimeout(() => toast.classList.add('hidden'), 2800);
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, options);
  if (!res.ok) {
    let detail = 'Ошибка запроса';
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

async function fetchOrders() {
  try {
    orders = await apiFetch('/orders');
    renderOrders();
  } catch (e) {
    console.error(e);
    showToast('Не удалось загрузить ленту');
  }
}

function renderOrders() {
  const query = searchInput.value.trim().toLowerCase();
  const filtered = orders.filter(o => {
    const matchQuery = `${o.title} ${o.description} ${o.author} ${o.price}`.toLowerCase().includes(query);
    const matchCategory = activeCategory ? o.type === activeCategory : true;
    return matchQuery && matchCategory;
  });

  ordersGrid.innerHTML = '';
  emptyState.classList.toggle('hidden', filtered.length > 0);

  filtered.forEach(order => {
    const isOwn = Number(order.author_id) === Number(currentUser.id);
    const initial = esc((order.author || '?').charAt(0).toUpperCase());
    ordersGrid.innerHTML += `
      <button type="button" onclick="openOrder(${order.id})"
        class="tap text-left order-card rounded-2xl p-3.5 min-h-[165px] flex flex-col justify-between w-full relative">
        ${isOwn ? '<span class="absolute top-2.5 right-2.5 text-[10px] bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">Моё</span>' : ''}
        <div>
          <p class="font-semibold text-[15px] leading-5 line-clamp-2 pr-8">${esc(order.title)}</p>
          <p class="text-[13px] text-gray-500 mt-1 line-clamp-3">${esc(order.description)}</p>
        </div>
        <div class="mt-2">
          <div class="flex items-center gap-1.5 min-w-0">
            <span class="shrink-0 w-5 h-5 rounded-full bg-[var(--lavender)] text-[var(--lavender-text)] text-[10px] font-bold flex items-center justify-center">${initial}</span>
            <span class="text-[12px] text-gray-500 truncate">${esc(order.author)}</span>
          </div>
          <div class="flex items-center justify-between gap-2 mt-1.5">
            <span class="text-[12px] text-gray-500">🙋 ${order.response_count || 0}</span>
            <span class="text-[13px] price-tag font-medium">Цена: ${Number(order.price).toLocaleString('ru-RU')} ₽</span>
          </div>
        </div>
      </button>`;
  });
}

window.filterCategory = function(cat) {
  activeCategory = activeCategory === cat ? null : cat;
  renderOrders();
};

searchInput.addEventListener('input', renderOrders);

const tabs = { feed: tabFeed, form: tabForm, profile: tabProfile };

function switchScreen(screen) {
  currentScreen = screen;
  screenFeed.classList.toggle('hidden', screen !== 'feed');
  screenForm.classList.toggle('hidden', screen !== 'form');
  screenProfile.classList.toggle('hidden', screen !== 'profile');

  Object.entries(tabs).forEach(([key, btn]) => {
    if (key === 'form') return; // FAB button keeps its own fixed style
    btn.classList.toggle('text-[var(--accent-dark)]', key === screen);
    btn.classList.toggle('text-gray-400', key !== screen);
  });

  if (screen === 'profile') loadMyOrders();
  window.scrollTo(0, 0);
}

tabFeed.addEventListener('click', () => switchScreen('feed'));
tabForm.addEventListener('click', () => switchScreen('form'));
tabProfile.addEventListener('click', () => switchScreen('profile'));

function checkForm() {
  const price = adPrice.value.trim();
  const validPrice = price !== '' && Number(price) >= 0 && Number.isFinite(Number(price));
  const hasText = adTitle.value.trim() && adDescription.value.trim() && adType.value;
  publishBtn.disabled = !(hasText && validPrice);
  priceError.classList.toggle('hidden', price === '' || validPrice);
}

[adTitle, adDescription, adPrice].forEach(el => el.addEventListener('input', checkForm));
adType.addEventListener('change', checkForm);

adPrice.addEventListener('input', () => {
  if (adPrice.value !== '' && Number(adPrice.value) < 0) adPrice.value = 0;
  checkForm();
});

publishBtn.addEventListener('click', async () => {
  const price = Number(adPrice.value);
  if (price < 0 || !Number.isFinite(price)) {
    priceError.classList.remove('hidden');
    return;
  }

  try {
    await apiFetch('/add_order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: adTitle.value.trim(),
        description: adDescription.value.trim(),
        type: adType.value,
        price,
        author: currentUser.name,
        author_id: currentUser.id
      })
    });

    adTitle.value = '';
    adDescription.value = '';
    adType.value = '';
    adPrice.value = '';
    priceError.classList.add('hidden');
    checkForm();
    switchScreen('feed');
    await fetchOrders();
    showToast('Объявление опубликовано');
  } catch (e) {
    showToast(e.message || 'Не удалось опубликовать объявление');
  }
});

async function openOrder(orderId) {
  detailOrderId = orderId;
  detailContent.innerHTML = '<div class="py-16 text-center text-gray-400">Загрузка…</div>';
  detailScreen.classList.remove('hidden');
  bottomNav.classList.add('hidden');
  window.scrollTo(0, 0);

  try {
    const order = await apiFetch(`/orders/${orderId}?viewer_id=${currentUser.id}`);
    renderOrderDetail(order);
    tg?.BackButton?.show();
    tg?.BackButton?.onClick(closeOrder);
  } catch (e) {
    detailContent.innerHTML = `<div class="py-16 text-center text-red-500">${esc(e.message)}</div>`;
  }
}

function renderOrderDetail(order) {
  const isOwner = Number(order.author_id) === Number(currentUser.id);
  const hasResponded = !!order.current_user_responded;

  const responseButton = isOwner
    ? `<div class="rounded-2xl bg-gray-100 p-4 text-sm text-gray-600">Это ваше объявление. Здесь отображаются все исполнители, которые согласились взять заказ.</div>`
    : hasResponded
      ? `<button type="button" onclick="refuseOrder(${order.id})"
           class="tap w-full rounded-full border-2 border-red-300 text-red-600 py-3 font-semibold">
           Отказаться от выполнения
         </button>`
      : `<button type="button" onclick="respondToOrder(${order.id})"
           class="tap w-full rounded-full bg-[var(--accent)] text-white py-3 font-semibold">
           Готов выполнить заказ
         </button>`;

  const responders = order.responders?.length
    ? order.responders.map((r, index) => `
        <div class="flex items-center gap-3 ${index ? 'border-t border-gray-100 pt-3 mt-3' : ''}">
          <div class="w-10 h-10 rounded-full bg-[var(--lavender)] text-[var(--lavender-text)] flex items-center justify-center font-semibold">
            ${esc((r.name || '?').charAt(0).toUpperCase())}
          </div>
          <div class="min-w-0">
            <p class="font-medium">${esc(r.name)}</p>
            <p class="text-sm text-gray-500">${esc(r.username || '@no_username')}${r.room ? ` · комната ${esc(r.room)}` : ''}</p>
          </div>
        </div>`).join('')
    : '<p class="text-sm text-gray-400">Пока никто не откликнулся.</p>';

  detailContent.innerHTML = `
    <div class="flex flex-wrap gap-2 mb-3">
      <span class="bg-gray-100 rounded-full px-3 py-1 text-xs font-medium">${esc(order.type)}</span>
      <span class="bg-green-100 text-green-700 rounded-full px-3 py-1 text-xs font-medium">${Number(order.price).toLocaleString('ru-RU')} ₽</span>
    </div>

    <h1 class="text-2xl font-bold leading-tight">${esc(order.title)}</h1>
    <p class="mt-4 whitespace-pre-wrap text-[15px] leading-6 text-gray-700">${esc(order.description)}</p>

    <div class="mt-6 rounded-2xl bg-gray-100 p-4">
      <p class="text-xs text-gray-500 uppercase tracking-wide">Заказчик</p>
      <p class="mt-1 font-semibold">${esc(order.author)}</p>
      ${order.author_username ? `<p class="text-sm text-gray-500">${esc(order.author_username)}</p>` : ''}
    </div>

    <div class="mt-5">
      ${responseButton}
    </div>

    <section class="mt-7">
      <div class="flex items-center justify-between">
        <h2 class="font-bold text-lg">Откликнулись</h2>
        <span class="text-sm text-gray-500">${order.response_count || 0}</span>
      </div>
      <div class="mt-3 rounded-2xl bg-gray-50 border border-gray-100 p-4">
        ${responders}
      </div>
    </section>
  `;
}

window.respondToOrder = async function(orderId) {
  try {
    const result = await apiFetch(`/orders/${orderId}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        telegram_id: currentUser.id,
        name: currentUser.name,
        username: currentUser.username
      })
    });
    tg?.HapticFeedback?.notificationOccurred('success');
    showToast(result.notification_sent ? 'Отклик отправлен владельцу' : 'Отклик сохранён');
    await openOrder(orderId);
    await fetchOrders();
  } catch (e) {
    tg?.HapticFeedback?.notificationOccurred('error');
    showToast(e.message || 'Не удалось отправить отклик');
  }
};

window.refuseOrder = async function(orderId) {
  try {
    await apiFetch(`/orders/${orderId}/respond`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telegram_id: currentUser.id })
    });
    tg?.HapticFeedback?.notificationOccurred('success');
    showToast('Вы отказались от выполнения');
    await openOrder(orderId);
    await fetchOrders();
  } catch (e) {
    showToast(e.message || 'Не удалось отказаться');
  }
};

function closeOrder() {
  detailScreen.classList.add('hidden');
  bottomNav.classList.remove('hidden');
  detailOrderId = null;
  tg?.BackButton?.hide();
}

detailBack.addEventListener('click', closeOrder);

async function initProfile() {
  profileName.textContent = currentUser.name;
  profileUsername.textContent = currentUser.username;
  userAvatar.textContent = currentUser.name[0]?.toUpperCase() || '?';

  try {
    const data = await apiFetch('/sync_user', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        telegram_id: currentUser.id,
        name: currentUser.name,
        username: currentUser.username
      })
    });
    profileRoom.value = data.room || '';
  } catch (e) {
    console.error(e);
  }
}

saveRoomBtn.addEventListener('click', async () => {
  try {
    await apiFetch('/update_profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        telegram_id: currentUser.id,
        room: profileRoom.value.trim()
      })
    });
    showToast('Профиль обновлён');
  } catch (e) {
    showToast('Не удалось обновить профиль');
  }
});

let myOrdersCache = [];
let showArchivedOnly = false;
const archiveToggleBtn = document.getElementById('archive-toggle-btn');
const archiveToggleLabel = document.getElementById('archive-toggle-label');

async function loadMyOrders() {
  try {
    myOrdersCache = await apiFetch(`/my_orders/${currentUser.id}`);
    renderMyOrders();
  } catch (e) {
    console.error(e);
    showToast('Ошибка загрузки своих объявлений');
  }
}

function renderMyOrders() {
  myOrdersList.innerHTML = '';
  archiveToggleLabel.textContent = showArchivedOnly ? 'Активные' : 'Архив';

  const list = myOrdersCache.filter(o => showArchivedOnly ? o.is_archived : !o.is_archived);

  if (list.length === 0) {
    myOrdersList.innerHTML = `<p class="text-gray-400 text-sm">${showArchivedOnly ? 'В архиве пока пусто' : 'У вас нет активных объявлений'}</p>`;
    return;
  }

  list.forEach(o => {
    const archiveStyles = o.is_archived ? 'opacity-60 bg-gray-50' : 'bg-gray-100';
    const archiveBadge = o.is_archived ? '<span class="text-orange-600 font-bold ml-2">(В архиве)</span>' : '';
    const restoreBtn = o.is_archived
      ? `<button onclick="restoreMyOrder(${o.id})" class="text-green-600 bg-green-100 rounded-lg text-xs font-semibold px-3 py-1.5 tap mb-1">Восстановить</button>`
      : '';

    myOrdersList.innerHTML += `
      <div class="${archiveStyles} rounded-2xl p-3.5 flex justify-between items-center border border-gray-200 transition-all">
        <button type="button" onclick="openOrder(${o.id})" class="text-left pr-2 min-w-0">
          <p class="font-medium text-sm">${esc(o.title)}</p>
          <p class="text-xs text-gray-500 mt-1">${esc(o.type)} • ${Number(o.price).toLocaleString('ru-RU')} ₽ • 🙋 ${o.response_count || 0} ${archiveBadge}</p>
        </button>
        <div class="flex flex-col items-end shrink-0">
          ${restoreBtn}
          <button onclick="deleteMyOrder(${o.id})" class="text-red-500 bg-red-50 rounded-lg text-xs font-semibold px-3 py-1.5 tap">Удалить</button>
        </div>
      </div>`;
  });
}

archiveToggleBtn.addEventListener('click', () => {
  showArchivedOnly = !showArchivedOnly;
  renderMyOrders();
});

window.restoreMyOrder = async function(orderId) {
  try {
    await apiFetch(`/restore_order/${orderId}`, { method: 'POST' });
    await loadMyOrders();
    await fetchOrders();
  } catch (e) {
    showToast('Не удалось восстановить объявление');
  }
};

window.deleteMyOrder = async function(orderId) {
  if (!confirm('Удалить объявление?')) return;
  try {
    await apiFetch(`/delete_order/${orderId}`, { method: 'DELETE' });
    await loadMyOrders();
    await fetchOrders();
  } catch (e) {
    showToast('Не удалось удалить объявление');
  }
};

initProfile();
fetchOrders();
checkForm();