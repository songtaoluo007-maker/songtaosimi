<template>
  <div>
    <el-alert
      title="成长报告功能将在后端 P3.5 完成后开放。届时将生成每周建议准确率、有效建议、失误判断和用户行为变化总结。"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 20px;"
    />

    <el-card shadow="hover">
      <template #header><span style="font-weight: bold;">AI 分析师成长报告</span></template>
      <el-empty description="暂无报告，等待后端报告服务接入" :image-size="80" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
</script>
