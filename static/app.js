const state = {
  token: localStorage.getItem("taskflow_token") || null,
  user: null,
  boards: [],
  activeBoardId: null,
  tasks: [],
  members: [],
  editingTaskId: null,
};

const $ = (id) => document.getElementById(id);

function toast(message, isError = false) {
  const holder = $("toast-holder");
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = message;
  holder.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const res = await fetch(`/api${path}`, { ...options, headers });

  if (res.status === 401) {
    logout();
    throw new Error("Session expired");
  }

  if (!res.ok) {
    let detail = "Something went wrong";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (e) {}
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

function initials(name) {
  return (name || "?").slice(0, 2).toUpperCase();
}

function showScreen(id) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  $(id).classList.add("active");
}

function openModal(id) {
  $("modal-backdrop").classList.remove("hidden");
  document.querySelectorAll(".modal").forEach((m) => m.classList.add("hidden"));
  $(id).classList.remove("hidden");
}

function closeModal() {
  $("modal-backdrop").classList.add("hidden");
}

document.querySelectorAll("[data-close-modal]").forEach((btn) => {
  btn.addEventListener("click", closeModal);
});

$("modal-backdrop").addEventListener("click", (e) => {
  if (e.target.id === "modal-backdrop") closeModal();
});

document.querySelectorAll(".auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".auth-tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".auth-form").forEach((f) => f.classList.remove("active"));
    tab.classList.add("active");
    $(`${tab.dataset.tab}-form`).classList.add("active");
  });
});

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("login-error").textContent = "";
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: $("login-email").value.trim(),
        password: $("login-password").value,
      }),
    });
    onAuthSuccess(data);
  } catch (err) {
    $("login-error").textContent = err.message;
  }
});

$("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("signup-error").textContent = "";
  try {
    const data = await api("/auth/signup", {
      method: "POST",
      body: JSON.stringify({
        username: $("signup-username").value.trim(),
        email: $("signup-email").value.trim(),
        password: $("signup-password").value,
      }),
    });
    onAuthSuccess(data);
  } catch (err) {
    $("signup-error").textContent = err.message;
  }
});

function onAuthSuccess(data) {
  state.token = data.access_token;
  state.user = data.user;
  localStorage.setItem("taskflow_token", state.token);
  boot();
}

function logout() {
  state.token = null;
  state.user = null;
  state.boards = [];
  state.activeBoardId = null;
  localStorage.removeItem("taskflow_token");
  showScreen("auth-screen");
}

$("logout-btn").addEventListener("click", logout);

async function boot() {
  try {
    state.user = await api("/auth/me");
  } catch (err) {
    showScreen("auth-screen");
    return;
  }

  $("user-name").textContent = state.user.username;
  $("user-avatar").textContent = initials(state.user.username);
  showScreen("app-screen");
  await loadBoards();
}

async function loadBoards() {
  state.boards = await api("/boards");
  renderBoardList();

  if (state.boards.length && !state.activeBoardId) {
    selectBoard(state.boards[0].id);
  } else if (!state.boards.length) {
    $("empty-state").classList.remove("hidden");
    $("board-view").classList.add("hidden");
  }
}

function renderBoardList() {
  const list = $("board-list");
  list.innerHTML = "";
  state.boards.forEach((board) => {
    const el = document.createElement("div");
    el.className = "board-list-item" + (board.id === state.activeBoardId ? " active" : "");
    el.textContent = board.name;
    el.addEventListener("click", () => selectBoard(board.id));
    list.appendChild(el);
  });
}

async function selectBoard(boardId) {
  state.activeBoardId = boardId;
  renderBoardList();

  const board = state.boards.find((b) => b.id === boardId);
  $("board-title").textContent = board.name;
  $("board-desc").textContent = board.description || "";

  $("empty-state").classList.add("hidden");
  $("board-view").classList.remove("hidden");

  await Promise.all([loadTasks(), loadMembers()]);
}

async function loadTasks() {
  state.tasks = await api(`/boards/${state.activeBoardId}/tasks`);
  renderTasks();
}

async function loadMembers() {
  const members = await api(`/boards/${state.activeBoardId}/members`);
  const board = state.boards.find((b) => b.id === state.activeBoardId);
  state.members = [{ user: { id: board.owner_id, username: "Owner" } }, ...members];

  const select = $("task-assignee-input");
  select.innerHTML = '<option value="">Unassigned</option>';
  const seen = new Set();
  state.members.forEach((m) => {
    if (seen.has(m.user.id)) return;
    seen.add(m.user.id);
    const opt = document.createElement("option");
    opt.value = m.user.id;
    opt.textContent = m.user.id === board.owner_id ? `${state.user.id === board.owner_id ? state.user.username : "Owner"}` : m.user.username;
    select.appendChild(opt);
  });
}

function assigneeName(userId) {
  if (!userId) return null;
  const board = state.boards.find((b) => b.id === state.activeBoardId);
  if (userId === board.owner_id && userId === state.user.id) return state.user.username;
  const m = state.members.find((mm) => mm.user.id === userId);
  return m ? m.user.username : "User";
}

function renderTasks() {
  ["todo", "in_progress", "done"].forEach((status) => {
    $(`list-${status}`).innerHTML = "";
  });

  const counts = { todo: 0, in_progress: 0, done: 0 };

  state.tasks.forEach((task) => {
    counts[task.status]++;
    const card = document.createElement("div");
    card.className = "task-card";
    card.addEventListener("click", () => openTaskModal(task));

    const title = document.createElement("div");
    title.className = "task-card-title";
    title.textContent = task.title;
    card.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "task-card-meta";
    if (task.assigned_to) {
      const av = document.createElement("div");
      av.className = "task-avatar";
      av.textContent = initials(assigneeName(task.assigned_to));
      meta.appendChild(av);
      const span = document.createElement("span");
      span.textContent = assigneeName(task.assigned_to);
      meta.appendChild(span);
    } else {
      const span = document.createElement("span");
      span.textContent = "Unassigned";
      meta.appendChild(span);
    }
    card.appendChild(meta);

    $(`list-${task.status}`).appendChild(card);
  });

  Object.keys(counts).forEach((status) => {
    $(`count-${status}`).textContent = counts[status];
  });
}

$("new-board-btn").addEventListener("click", () => {
  $("board-name-input").value = "";
  $("board-desc-input").value = "";
  openModal("board-modal");
});

$("board-modal-submit").addEventListener("click", async () => {
  const name = $("board-name-input").value.trim();
  if (!name) return toast("Board name is required", true);

  try {
    const board = await api("/boards", {
      method: "POST",
      body: JSON.stringify({ name, description: $("board-desc-input").value.trim() }),
    });
    closeModal();
    await loadBoards();
    selectBoard(board.id);
    toast("Board created");
  } catch (err) {
    toast(err.message, true);
  }
});

$("add-task-btn").addEventListener("click", () => openTaskModal(null));

function openTaskModal(task) {
  state.editingTaskId = task ? task.id : null;
  $("task-modal-title").textContent = task ? "Edit task" : "New task";
  $("task-title-input").value = task ? task.title : "";
  $("task-desc-input").value = task ? task.description : "";
  $("task-assignee-input").value = task && task.assigned_to ? task.assigned_to : "";
  $("task-status-input").value = task ? task.status : "todo";
  $("task-delete-btn").style.display = task ? "block" : "none";
  openModal("task-modal");
}

$("task-modal-submit").addEventListener("click", async () => {
  const title = $("task-title-input").value.trim();
  if (!title) return toast("Task title is required", true);

  const payload = {
    title,
    description: $("task-desc-input").value.trim(),
    assigned_to: $("task-assignee-input").value ? parseInt($("task-assignee-input").value) : null,
    status: $("task-status-input").value,
  };

  try {
    if (state.editingTaskId) {
      await api(`/tasks/${state.editingTaskId}`, { method: "PATCH", body: JSON.stringify(payload) });
      toast("Task updated");
    } else {
      await api(`/boards/${state.activeBoardId}/tasks`, { method: "POST", body: JSON.stringify(payload) });
      toast("Task created");
    }
    closeModal();
    await loadTasks();
  } catch (err) {
    toast(err.message, true);
  }
});

$("task-delete-btn").addEventListener("click", async () => {
  if (!state.editingTaskId) return;
  try {
    await api(`/tasks/${state.editingTaskId}`, { method: "DELETE" });
    closeModal();
    await loadTasks();
    toast("Task deleted");
  } catch (err) {
    toast(err.message, true);
  }
});

$("invite-btn").addEventListener("click", () => {
  $("invite-email-input").value = "";
  openModal("invite-modal");
});

$("invite-modal-submit").addEventListener("click", async () => {
  const email = $("invite-email-input").value.trim();
  if (!email) return toast("Email is required", true);

  try {
    await api(`/boards/${state.activeBoardId}/members`, {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    closeModal();
    await loadMembers();
    toast("Teammate added to the board");
  } catch (err) {
    toast(err.message, true);
  }
});

if (state.token) {
  boot();
} else {
  showScreen("auth-screen");
}
