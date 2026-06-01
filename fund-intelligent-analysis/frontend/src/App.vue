<template>
  <el-container class="app-shell">
    <el-aside width="232px" class="sidebar">
      <div class="brand">
        <div class="brand-mark">AI</div>
        <div>
          <strong>基金智能分析</strong>
          <span>本地私人系统</span>
        </div>
      </div>
      <el-menu
        :default-active="activeRoute"
        router
        background-color="transparent"
        text-color="#9aa7b8"
        active-text-color="#ffffff"
        class="nav-menu"
      >
        <!-- 核心 -->
        <div class="menu-group-label">核心</div>
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/holdings">
          <el-icon><Wallet /></el-icon>
          <span>持仓管理</span>
        </el-menu-item>
        <el-menu-item index="/ai-analyst">
          <el-icon><MagicStick /></el-icon>
          <span>AI 分析师</span>
        </el-menu-item>

        <!-- 市场 -->
        <div class="menu-group-label">市场</div>
        <el-menu-item index="/market">
          <el-icon><TrendCharts /></el-icon>
          <span>行情监控</span>
        </el-menu-item>
        <el-menu-item index="/news">
          <el-icon><Document /></el-icon>
          <span>新闻资讯</span>
        </el-menu-item>

        <!-- 数据 -->
        <div class="menu-group-label">数据</div>
        <el-menu-item index="/ocr-import">
          <el-icon><Camera /></el-icon>
          <span>截图导入</span>
        </el-menu-item>
        <el-menu-item index="/trades">
          <el-icon><List /></el-icon>
          <span>交易记录</span>
        </el-menu-item>

        <!-- 系统 -->
        <div class="menu-group-label">系统</div>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-footer">
        <span>Local only</span>
        <strong>127.0.0.1:8000</strong>
      </div>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeRoute = computed(() => {
  // /ai-analyst 保持高亮
  if (route.path.startsWith('/ai-analyst') || route.path.startsWith('/ai-advisor')) {
    return '/ai-analyst'
  }
  return route.path
})
</script>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f3f6fa;
}

.app-shell {
  height: 100vh;
  background: #f3f6fa;
}

.sidebar {
  background: #111827;
  color: #fff;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.brand {
  height: 78px;
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #2f6fef;
  display: grid;
  place-items: center;
  font-weight: 800;
}

.brand strong,
.brand span,
.sidebar-footer span,
.sidebar-footer strong {
  display: block;
}

.brand strong {
  font-size: 16px;
}

.brand span,
.sidebar-footer span {
  margin-top: 3px;
  color: #9aa7b8;
  font-size: 12px;
}

.nav-menu {
  border: 0 !important;
  padding: 12px;
  flex: 1;
}

.menu-group-label {
  color: #5a6a7e;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 16px 12px 6px;
}

.nav-menu .el-menu-item {
  border-radius: 8px;
  margin-bottom: 4px;
  height: 44px;
}

.nav-menu .el-menu-item.is-active {
  background: #2f6fef !important;
}

.nav-menu .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.08) !important;
}

.sidebar-footer {
  margin: 12px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
}

.sidebar-footer span {
  display: block;
}

.sidebar-footer strong {
  display: block;
  margin-top: 2px;
  font-size: 13px;
}

.main {
  padding: 24px;
  overflow-y: auto;
}
</style>
