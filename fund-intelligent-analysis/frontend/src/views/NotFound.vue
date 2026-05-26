<template>
  <div class="not-found">
    <h1>404</h1>
    <p>页面不存在</p>
    <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60vh;
  color: var(--el-text-color-secondary);
}
.not-found h1 {
  font-size: 72px;
  margin: 0 0 16px;
  color: var(--el-color-primary);
}
.not-found p {
  font-size: 18px;
  margin: 0 0 24px;
}
</style>
