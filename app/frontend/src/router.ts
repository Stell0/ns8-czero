import { createRouter, createWebHistory } from 'vue-router'
import { basePath } from './api/client'

export const router = createRouter({
  history: createWebHistory(`${basePath}/`),
  routes: [
    {
      path: '/',
      component: () => import('./views/HomeView.vue'),
      meta: { title: 'nav.home' },
    },
    {
      path: '/search',
      component: () => import('./views/SearchView.vue'),
      meta: { title: 'search.results' },
    },
    {
      path: '/wiki/:id?',
      component: () => import('./views/WikiView.vue'),
      meta: { title: 'nav.wiki' },
    },
    {
      path: '/sources/:id?',
      component: () => import('./views/SourcesView.vue'),
      meta: { title: 'nav.sources' },
    },
    {
      path: '/evidence/:id',
      component: () => import('./views/EvidenceView.vue'),
      meta: { title: 'reader.evidence' },
    },
    {
      path: '/tables/:type?',
      component: () => import('./views/TablesView.vue'),
      meta: { title: 'nav.tables' },
    },
    {
      path: '/projects',
      component: () => import('./views/ProjectsView.vue'),
      meta: { title: 'nav.projects' },
    },
    {
      path: '/explore/:kind?/:id?',
      component: () => import('./views/ExploreView.vue'),
      meta: { title: 'nav.explore' },
    },
    {
      path: '/account',
      component: () => import('./views/AccountView.vue'),
      meta: { title: 'nav.account' },
    },
    {
      path: '/agents',
      component: () => import('./views/AgentsView.vue'),
      meta: { title: 'nav.agents', public: true, optionalSession: true },
    },
    {
      path: '/admin/:area?',
      component: () => import('./views/AdminView.vue'),
      meta: { title: 'nav.admin', admin: true },
    },
    {
      path: '/auth/sign-in',
      component: () => import('./views/SignInView.vue'),
      meta: { title: 'account.signin', public: true },
    },
    {
      path: '/auth/:result(callback|login)',
      component: () => import('./views/AuthErrorView.vue'),
      meta: { title: 'account.signin', public: true },
    },
    {
      path: '/oauth/:flow',
      component: () => import('./views/ConsentView.vue'),
      meta: { title: 'consent.title' },
    },
  ],
  scrollBehavior(to, _from, saved) {
    return saved || (to.hash ? { el: to.hash } : { top: 0 })
  },
})

router.beforeEach((to, from) => {
  if (
    !('space_id' in to.query) &&
    from.query.space_id &&
    to.path !== '/auth/sign-in'
  ) {
    return { ...to, query: { ...to.query, space_id: from.query.space_id } }
  }
})
