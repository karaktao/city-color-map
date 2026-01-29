import axios from 'axios'

const service = axios.create({
  baseURL: '/',     // 走 Vite 代理
  timeout: 600000,  // 有些步骤比较久，时间给长点
})

export default service
