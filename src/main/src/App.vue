<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <nav class="navbar">
    <div class="navbar-brand">
        <i class="fas fa-snowflake"></i>
        <span>高效机房全年能耗仿真分析平台</span>
    </div>
    <div>
        <a href="#" class="nav-link active" data-tab="home"><i class="fas fa-home"></i> 首页</a>
        <a href="#" class="nav-link" data-tab="load-analysis"><i class="fas fa-chart-line"></i> 建筑冷负荷分析</a>
        <a href="#" class="nav-link" data-tab="design-settings"><i class="fas fa-cogs"></i> 高效机房设计方案</a>
        <a href="#" class="nav-link" data-tab="control-settings"><i class="fas fa-sliders-h"></i> 群控系统控制方案</a>
        <a href="#" class="nav-link" data-tab="result-analysis"><i class="fas fa-chart-pie"></i> 仿真结果分析</a>
    </div>
  </nav>

  <RouterView />
</template>

<style scoped>
.navbar {
    background: rgba(241, 8, 8, 0.1);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    padding: 1rem 2rem;
    color: white;
    position: sticky;
    top: 0;
    z-index: 50;
}
</style>
