/**
 * 認証モジュール
 * JWTトークン管理とユーザー状態を提供
 */

const Auth = {
    // トークンのローカルストレージキー
    TOKEN_KEY: 'card_price_token',
    USER_KEY: 'card_price_user',

    /**
     * トークンを保存
     */
    setToken(token) {
        localStorage.setItem(this.TOKEN_KEY, token);
    },

    /**
     * トークンを取得
     */
    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    /**
     * トークンを削除
     */
    removeToken() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);
    },

    /**
     * ユーザー情報を保存
     */
    setUser(user) {
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    },

    /**
     * ユーザー情報を取得
     */
    getUser() {
        const userStr = localStorage.getItem(this.USER_KEY);
        return userStr ? JSON.parse(userStr) : null;
    },

    /**
     * ログイン済みかチェック
     */
    isLoggedIn() {
        return !!this.getToken();
    },

    /**
     * 管理者かチェック
     */
    isAdmin() {
        const user = this.getUser();
        return user && user.role === 'admin';
    },

    /**
     * 認証ヘッダーを取得
     */
    getAuthHeaders() {
        const token = this.getToken();
        if (!token) return {};
        return {
            'Authorization': `Bearer ${token}`
        };
    },

    /**
     * ログイン
     */
    async login(username, password) {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'ログインに失敗しました');
        }

        this.setToken(data.access_token);
        // ログイン直後はトークンが有効なはずなので、エラーでもトークンを削除しない
        await this.fetchCurrentUser(false);

        return data;
    },

    /**
     * ユーザー登録
     */
    async register(username, email, password) {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '登録に失敗しました');
        }

        this.setToken(data.access_token);
        await this.fetchCurrentUser(false);
        return data;
    },

    /**
     * 管理者登録
     */
    async adminRegister(username, email, password, inviteCode) {
        const response = await fetch('/api/auth/admin-register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username,
                email,
                password,
                invite_code: inviteCode
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '管理者登録に失敗しました');
        }

        this.setToken(data.access_token);
        await this.fetchCurrentUser(false);
        return data;
    },

    /**
     * 現在のユーザー情報を取得
     * @param {boolean} removeTokenOnError - エラー時にトークンを削除するか（デフォルト: true）
     */
    async fetchCurrentUser(removeTokenOnError = true) {
        const token = this.getToken();
        if (!token) return null;

        try {
            const response = await fetch('/api/auth/me', {
                headers: this.getAuthHeaders()
            });

            if (!response.ok) {
                if (removeTokenOnError) {
                    this.removeToken();
                }
                return null;
            }

            const user = await response.json();
            this.setUser(user);
            return user;
        } catch (e) {
            console.error('Failed to fetch user:', e);
            return null;
        }
    },

    /**
     * ログアウト
     */
    logout() {
        this.removeToken();
        window.location.href = '/';
    },

    /**
     * 認証が必要なAPI呼び出し
     */
    async authFetch(url, options = {}) {
        const headers = {
            ...options.headers,
            ...this.getAuthHeaders()
        };

        const response = await fetch(url, { ...options, headers });

        // 401の場合はトークンをクリア
        if (response.status === 401) {
            this.removeToken();
            window.location.href = '/login';
            throw new Error('認証が必要です');
        }

        return response;
    }
};

/**
 * お気に入り管理モジュール
 */
const Favorites = {
    // お気に入りIDのキャッシュ
    _cachedIds: null,

    /**
     * お気に入りIDリストを取得
     */
    async getIds() {
        if (!Auth.isLoggedIn()) return [];
        if (this._cachedIds !== null) return this._cachedIds;

        try {
            const response = await Auth.authFetch('/api/favorites/ids');
            if (!response.ok) return [];
            const data = await response.json();
            this._cachedIds = data.card_ids || [];
            return this._cachedIds;
        } catch (e) {
            console.error('Failed to fetch favorite ids:', e);
            return [];
        }
    },

    /**
     * お気に入り一覧を取得
     */
    async getAll() {
        if (!Auth.isLoggedIn()) return [];

        try {
            const response = await Auth.authFetch('/api/favorites');
            if (!response.ok) return [];
            const data = await response.json();
            return data.favorites || [];
        } catch (e) {
            console.error('Failed to fetch favorites:', e);
            return [];
        }
    },

    /**
     * お気に入りに追加
     */
    async add(cardId) {
        const response = await Auth.authFetch('/api/favorites', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ card_id: cardId })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || '追加に失敗しました');
        }

        // キャッシュを更新
        if (this._cachedIds) {
            this._cachedIds.push(cardId);
        }

        return await response.json();
    },

    /**
     * お気に入りから削除
     */
    async remove(cardId) {
        const response = await Auth.authFetch(`/api/favorites/${cardId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || '削除に失敗しました');
        }

        // キャッシュを更新
        if (this._cachedIds) {
            this._cachedIds = this._cachedIds.filter(id => id !== cardId);
        }

        return await response.json();
    },

    /**
     * お気に入り状態を切り替え
     */
    async toggle(cardId) {
        const ids = await this.getIds();
        if (ids.includes(cardId)) {
            return await this.remove(cardId);
        } else {
            return await this.add(cardId);
        }
    },

    /**
     * お気に入りかチェック
     */
    async isFavorite(cardId) {
        const ids = await this.getIds();
        return ids.includes(cardId);
    },

    /**
     * キャッシュをクリア
     */
    clearCache() {
        this._cachedIds = null;
    }
};

/**
 * ユーザーメニューUIを更新
 */
async function updateUserMenu() {
    const userMenuEl = document.getElementById('user-menu');
    if (!userMenuEl) return;

    if (Auth.isLoggedIn()) {
        let user = Auth.getUser();

        if (!user) {
            user = await Auth.fetchCurrentUser();
        }

        if (user) {
            userMenuEl.innerHTML = `
                <div class="notification-bell" id="notification-bell">
                    <button class="bell-btn" onclick="toggleNotifications(event)">
                        <span class="bell-icon">&#128276;</span>
                        <span class="notification-badge hidden" id="notification-badge">0</span>
                    </button>
                    <div class="notification-dropdown hidden" id="notification-dropdown">
                        <div class="notification-header">
                            <span>通知</span>
                            <button class="mark-all-read" onclick="markAllNotificationsRead()">全て既読</button>
                        </div>
                        <div class="notification-list" id="notification-list">
                            <div class="notification-loading">読み込み中...</div>
                        </div>
                    </div>
                </div>
                <div class="user-menu-dropdown">
                    <button class="user-menu-btn">
                        <span class="user-icon">&#128100;</span>
                        <span class="user-name">${escapeHtml(user.username)}</span>
                        ${user.role === 'admin' ? '<span class="admin-badge">Admin</span>' : ''}
                    </button>
                    <div class="user-menu-content">
                        <a href="/favorites" class="menu-item">&#9734; お気に入り</a>
                        ${user.role === 'admin' ? '<a href="/admin" class="menu-item">&#9881; 管理画面</a>' : ''}
                        <button class="menu-item logout-btn" onclick="Auth.logout()">&#8594; ログアウト</button>
                    </div>
                </div>
            `;

            // ドロップダウンの開閉
            const btn = userMenuEl.querySelector('.user-menu-btn');
            const content = userMenuEl.querySelector('.user-menu-content');
            if (btn && content) {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    content.classList.toggle('show');
                    // 通知ドロップダウンを閉じる
                    document.getElementById('notification-dropdown')?.classList.add('hidden');
                });
                document.addEventListener('click', (e) => {
                    if (!e.target.closest('.user-menu-dropdown')) {
                        content.classList.remove('show');
                    }
                    if (!e.target.closest('.notification-bell')) {
                        document.getElementById('notification-dropdown')?.classList.add('hidden');
                    }
                });
            }

            // 通知数を取得
            updateNotificationCount();
        } else {
            // トークンが無効な場合
            showLoginButton(userMenuEl);
        }
    } else {
        showLoginButton(userMenuEl);
    }
}

/**
 * 通知数を更新
 */
async function updateNotificationCount() {
    try {
        const response = await fetch('/api/notifications/count', {
            headers: Auth.getAuthHeaders()
        });
        if (response.ok) {
            const data = await response.json();
            const badge = document.getElementById('notification-badge');
            if (badge) {
                if (data.unread_count > 0) {
                    badge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
                    badge.classList.remove('hidden');
                } else {
                    badge.classList.add('hidden');
                }
            }
        }
    } catch (e) {
        console.error('Failed to fetch notification count:', e);
    }
}

/**
 * 通知ドロップダウンを開閉
 */
function toggleNotifications(e) {
    e.stopPropagation();
    const dropdown = document.getElementById('notification-dropdown');
    const userContent = document.querySelector('.user-menu-content');

    if (dropdown.classList.contains('hidden')) {
        dropdown.classList.remove('hidden');
        userContent?.classList.remove('show');
        loadNotifications();
    } else {
        dropdown.classList.add('hidden');
    }
}

/**
 * 通知一覧を読み込み
 */
async function loadNotifications() {
    const listEl = document.getElementById('notification-list');
    if (!listEl) return;

    try {
        const response = await fetch('/api/notifications?limit=20', {
            headers: Auth.getAuthHeaders()
        });
        if (!response.ok) throw new Error('Failed to load notifications');

        const data = await response.json();
        if (data.notifications.length === 0) {
            listEl.innerHTML = '<div class="notification-empty">通知はありません</div>';
            return;
        }

        listEl.innerHTML = data.notifications.map(n => `
            <div class="notification-item ${n.is_read ? 'read' : 'unread'}" data-id="${n.id}" onclick="handleNotificationClick(${n.id}, ${n.card_id || 'null'})">
                <div class="notification-title">${escapeHtml(n.title)}</div>
                <div class="notification-message">${escapeHtml(n.message)}</div>
                <div class="notification-time">${formatNotificationTime(n.created_at)}</div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load notifications:', e);
        listEl.innerHTML = '<div class="notification-error">読み込みに失敗しました</div>';
    }
}

/**
 * 通知クリック処理
 */
async function handleNotificationClick(notificationId, cardId) {
    // 既読にする
    try {
        await fetch(`/api/notifications/${notificationId}/read`, {
            method: 'POST',
            headers: Auth.getAuthHeaders()
        });
        updateNotificationCount();
    } catch (e) {
        console.error('Failed to mark notification as read:', e);
    }

    // カードページに遷移
    if (cardId) {
        window.location.href = `/card/${cardId}`;
    }
}

/**
 * 全通知を既読にする
 */
async function markAllNotificationsRead() {
    try {
        await fetch('/api/notifications/read-all', {
            method: 'POST',
            headers: Auth.getAuthHeaders()
        });
        updateNotificationCount();
        // 通知リストを更新
        document.querySelectorAll('.notification-item.unread').forEach(el => {
            el.classList.remove('unread');
            el.classList.add('read');
        });
    } catch (e) {
        console.error('Failed to mark all notifications as read:', e);
    }
}

/**
 * 通知時間をフォーマット
 */
function formatNotificationTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'たった今';
    if (minutes < 60) return `${minutes}分前`;
    if (hours < 24) return `${hours}時間前`;
    if (days < 7) return `${days}日前`;
    return date.toLocaleDateString('ja-JP');
}

function showLoginButton(el) {
    el.innerHTML = `
        <a href="/login" class="login-link">ログイン</a>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ページ読み込み時にユーザーメニューを更新
document.addEventListener('DOMContentLoaded', updateUserMenu);
