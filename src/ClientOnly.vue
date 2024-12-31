<!-- src/components/ClientOnly.vue -->
<template>
    <div v-if="isClient"><slot /></div>
  </template>
  
  <script setup lang="ts">
  import { ref, onMounted } from 'vue'
  
  const isClient = ref(false)
  
  onMounted(() => {
    isClient.value = true
  })
  </script>
  