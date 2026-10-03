<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>({})
onMounted(async () => { s.value = await api('/refills/summary?location_id=1') })
</script>
<template>
  <h1>汇总</h1>
  <p class="sub">本点位补货建议合计</p>
  <div class="card grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem">
    <div><div class="muted">建议补货总量</div><div class="stat">{{ s.total_fill }}</div></div>
    <div><div class="muted">待补货道</div><div class="stat">{{ s.need_fill_count }}</div></div>
    <div><div class="muted">满仓货道</div><div class="stat">{{ s.full_count }}</div></div>
    <div><div class="muted">超占货道</div><div class="stat">{{ s.overbooked_count }}</div></div>
    <div><div class="muted">封锁货道</div><div class="stat">{{ s.blocked_count }}</div></div>
  </div>
</template>
