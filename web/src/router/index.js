import { createRouter, createWebHistory } from 'vue-router'
import CityColorWizard from '../pages/CityColorWizard.vue'

const routes = [
  {
    path: '/',
    name: 'wizard',
    component: CityColorWizard
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
