<template>
    <div id="widget-container"></div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { HTMLManager } from '@jupyter-widgets/html-manager'

onMounted(async () => {
// Create a new HTML Manager.
const manager = new HTMLManager()

// Assume your Pyodide code stores the widget model in window.widget_model.
// You need to implement the mechanism in your Python code.
const widgetModel = window.widget_model 
if (widgetModel) {
    const container = document.getElementById('widget-container')
    if (container) {
    await manager.display_view(widgetModel, container)
    } else {
    console.error("Widget container not found")
    }
} else {
    console.error("No widget model found in window.widget_model")
}
})
</script>

<style scoped>
#widget-container {
margin: 16px;
}
</style>
