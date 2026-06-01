<template>
  <div>
    <el-alert
      title="相似案例检索功能将在后端 P3.4 完成后开放。届时将自动匹配历史相似市场场景和建议。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 20px;"
    />

    <el-card shadow="hover">
      <template #header><span style="font-weight: bold;">历史相似案例</span></template>
      <el-empty description="暂无历史案例，等待后端相似度检索服务接入" :image-size="80" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
</script>
