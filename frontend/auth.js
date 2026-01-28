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
        await this.fetchCurrentUser();
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
        await this.fetchCurrentUser();
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
        await this.fetchCurrentUser();
        return data;
    },

    /**
     * 現在のユーザー情報を取得
     */
    async fetchCurrentUser() {
        if (!this.getToken()) return null;

        try {
            const response = await fetch('/api/auth/me', {
                headers: this.getAuthHeaders()
            });

            if (!response.ok) {
                this.removeToken();
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
        const user = Auth.getUser() || await Auth.fetchCurrentUser();
        if (user) {
            userMenuEl.innerHTML = `
                <div class="user-menu-dropdown">
                    <button class="user-menu-btn">
                        <span class="user-icon">&#128100;</span>
                        <span class="user-name">${escapeHtml(user.username)}</span>
                        ${user.role === 'admin' ? '<span class="admin-badge">管理者</span>' : ''}
                    </button>
                    <div class="user-menu-content">
                        <a href="/favorites" class="menu-item">お気に入り</a>
                        ${user.role === 'admin' ? '<a href="/admin" class="menu-item">管理画面</a>' : ''}
                        <button class="menu-item logout-btn" onclick="Auth.logout()">ログアウト</button>
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
                });
                document.addEventListener('click', () => {
                    content.classList.remove('show');
                });
            }
        } else {
            // トークンが無効な場合
            showLoginButton(userMenuEl);
        }
    } else {
        showLoginButton(userMenuEl);
    }
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
