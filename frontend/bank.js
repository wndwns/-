/* ==========================================================================
   工银牧融 · 银行版控制台（/bank）
   --------------------------------------------------------------------------
   数据全部来自 /api/bank/*（backend/bank_view.py 聚合）。
   页面结构遵循 L1 结论 / L2 动作 / L3 折叠依据三层，页面上不写解释性文字。
   ========================================================================== */
(function () {
  'use strict';

  // vue.global.prod.js 暴露的是 Vue 全局对象（不是裸的 createApp）
  var createApp = window.Vue && window.Vue.createApp;
  if (!createApp) {
    console.error('Vue 未加载：检查 ./vendor/vue.global.prod.js 是否可达');
    return;
  }

  var API = {
    overview: '/api/bank/overview',
    pool: '/api/bank/customer-pool',
    profile: function (n) { return '/api/bank/customer/' + encodeURIComponent(n); },
    docs: function (n) { return '/api/bank/customer/' + encodeURIComponent(n) + '/documents'; },
    ledger: '/api/bank/ledger',
    postloan: '/api/bank/post-loan',
    insurance: '/api/bank/insurance',
    regions: '/api/bank/regions'
  };

  function get(url) {
    return fetch(url, { headers: { Accept: 'application/json' } }).then(function (r) {
      if (!r.ok) { throw new Error(url + ' -> ' + r.status); }
      return r.json();
    });
  }

  createApp({
    data: function () {
      return {
        page: 'dashboard',
        tab: 'ov',
        navGroups: [
          { title: '获客与授信', items: [
            { page: 'dashboard', name: '工作台' },
            { page: 'pool', name: '客户池' },
            { page: 'profile', name: '客户档案' }
          ]},
          { title: '资产与风控', items: [
            { page: 'ledger', name: '活体资产台账' },
            { page: 'postloan', name: '贷后待办' },
            { page: 'region', name: '区域与集中度' }
          ]},
          { title: '协同', items: [
            { page: 'insurance', name: '保险协同' }
          ]}
        ],
        tabs: [
          { key: 'ov', name: '概览' }, { key: 'doc', name: '资料' },
          { key: 'asset', name: '资产' }, { key: 'credit', name: '授信' },
          { key: 'pl', name: '贷后' }, { key: 'ev', name: '依据' }
        ],
        crumb: '工作台',
        error: '',
        ov: {}, pool: { customers: [], sources: [] },
        profile: {}, docs: { items: [], groups: [], summary: {} },
        currentName: '',
        led: {}, post: { queue: [], by_level: {} }, ins: { queue: [], claims: [], discount_tiers: [] },
        reg: { rows: [] }
      };
    },

    computed: {
      crumbText: function () {
        var self = this;
        var found = '';
        this.navGroups.forEach(function (g) {
          g.items.forEach(function (i) { if (i.page === self.page) { found = i.name; } });
        });
        return found;
      }
    },

    watch: {
      crumbText: function (v) { this.crumb = v; }
    },

    mounted: function () {
      this.crumb = '工作台';
      var self = this;
      // 首屏只加载工作台需要的两块数据
      Promise.all([this.loadOverview(), this.loadPostLoan(), this.loadPool()])
        .catch(function (e) { self.error = String(e.message || e); });
    },

    methods: {
      /* ---------------- 通用 ---------------- */
      fail: function (e) {
        this.error = String((e && e.message) || e);
        console.error(e);
      },
      nav: function (p) {
        this.page = p;
        this.crumb = this.crumbText;
        window.scrollTo(0, 0);
        if (p === 'ledger') { this.loadLedger(); }
        if (p === 'postloan') { this.loadPostLoan(); }
        if (p === 'insurance') { this.loadInsurance(); }
        if (p === 'region') { this.loadRegions(); }
        if (p === 'pool') { this.loadPool(); }
        if (p === 'profile') { this.enterProfile(); }
      },
      /** 进入客户档案：保证有当前客户且数据已加载（从侧栏直接进来时也要有数据）。 */
      enterProfile: function () {
        var self = this;
        var go = function () {
          if (self.currentName) { self.loadProfile(); }
        };
        if (this.currentName) { go(); return; }
        if ((this.pool.customers || []).length) { go(); return; }
        this.loadPool().then(function () { self.loadProfile(); });
      },
      badge: function (page) {
        if (page === 'postloan' && this.post.total) { return this.post.total; }
        if (page === 'pool' && this.pool.total) { return this.pool.total; }
        if (page === 'insurance' && this.ins.pending_count) { return this.ins.pending_count; }
        return '';
      },

      /* ---------------- 加载 ---------------- */
      loadOverview: function () {
        var self = this;
        return get(API.overview).then(function (d) { self.ov = d; }).catch(function (e) { self.fail(e); });
      },
      loadPool: function () {
        var self = this;
        return get(API.pool).then(function (d) {
          self.pool = d;
          if (!self.currentName && d.customers.length) {
            self.currentName = d.customers[0].subject_name;
          }
        }).catch(function (e) { self.fail(e); });
      },
      loadProfile: function () {
        if (!this.currentName) { return Promise.resolve(); }
        var self = this, name = this.currentName;
        return Promise.all([get(API.profile(name)), get(API.docs(name))])
          .then(function (res) { self.profile = res[0]; self.docs = res[1]; })
          .catch(function (e) { self.fail(e); });
      },
      loadLedger: function () {
        var self = this;
        return get(API.ledger).then(function (d) { self.led = d; }).catch(function (e) { self.fail(e); });
      },
      loadPostLoan: function () {
        var self = this;
        return get(API.postloan).then(function (d) { self.post = d; }).catch(function (e) { self.fail(e); });
      },
      loadInsurance: function () {
        var self = this;
        return get(API.insurance).then(function (d) { self.ins = d; }).catch(function (e) { self.fail(e); });
      },
      loadRegions: function () {
        var self = this;
        return get(API.regions).then(function (d) { self.reg = d; }).catch(function (e) { self.fail(e); });
      },

      /* ---------------- 客户切换 ---------------- */
      openCustomer: function (name) {
        if (!name) { return; }
        this.currentName = name;
        this.page = 'profile';
        this.tab = 'ov';
        this.crumb = '客户档案';
        window.scrollTo(0, 0);
        this.loadProfile();
      },
      stepCustomer: function (delta) {
        var list = this.pool.customers || [];
        if (!list.length) { return; }
        var idx = 0;
        for (var i = 0; i < list.length; i++) {
          if (list[i].subject_name === this.currentName) { idx = i; }
        }
        idx = (idx + delta + list.length) % list.length;
        this.openCustomer(list[idx].subject_name);
      },
      docItemsIn: function (group) {
        return (this.docs.items || []).filter(function (i) { return i.group === group; });
      },
      countBy: function (status) {
        var n = 0;
        (this.pool.customers || []).forEach(function (c) { if (c.conclusion_status === status) { n++; } });
        return n;
      },

      /* ---------------- 格式化 ---------------- */
      wan: function (yuan) {
        if (!yuan) { return '—'; }
        return (yuan / 10000).toFixed(0) + ' 万元';
      },
      fmtWan: function (v) {
        if (v === null || v === undefined || v === '') { return '—'; }
        return v + ' 万元';
      },
      pctCls: function (p) {
        p = Number(p) || 0;
        return p >= 80 ? 'ok' : (p >= 60 ? 'warn' : 'danger');
      },
      levelCls: function (lv) {
        return lv === '高' ? 'b-danger' : (lv === '中' ? 'b-warn' : 'b-info');
      },
      evidenceCls: function (s) {
        if (s === '已获取') { return 'b-ok'; }
        if (s === '部分') { return 'b-warn'; }
        return 'b-danger';
      },
      docCls: function (s) {
        if (s === '已填') { return 'b-ok'; }
        if (s === '待核验') { return 'b-warn'; }
        return 'b-danger';
      },
      ratioColor: function (p) {
        return p >= 40 ? 'var(--danger)' : (p >= 20 ? 'var(--warn)' : 'var(--red)');
      },
      sourceHint: function (s) {
        var map = {
          '政府数据匹配': '在保险台账的登记主体里出现过，行内无授信记录',
          '产业链反推': '在产业链交易记录里出现过，可从核心企业交易反推',
          '存量客户转介': '行内已有授信记录的存量客户',
          '自助测额度留资': '客户端自助测算后留下联系方式'
        };
        return map[s] || '—';
      }
    }
  }).mount('#app');
})();
