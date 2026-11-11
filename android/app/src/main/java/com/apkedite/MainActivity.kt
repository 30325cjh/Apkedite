package com.apkedite

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.documentfile.provider.DocumentFile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.zip.ZipInputStream

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { ApkEditorScreen() } }
    }
}

@Composable
private fun ApkEditorScreen() {
    val context = LocalContext.current
    var apkUri by remember { mutableStateOf<Uri?>(null) }
    var apkName by remember { mutableStateOf("No APK selected") }
    var entries by remember { mutableStateOf(listOf<String>()) }
    var selected by remember { mutableStateOf<String?>(null) }
    var editorText by remember { mutableStateOf("") }
    var query by remember { mutableStateOf("") }
    var edits by remember { mutableStateOf(mapOf<String, String>()) }
    var loading by remember { mutableStateOf(false) }
    var info by remember { mutableStateOf("Choose an APK to inspect its archive.") }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        if (uri != null) {
            val payload = org.json.JSONObject(edits).toString(2)
            context.contentResolver.openOutputStream(uri)?.use { it.write(payload.toByteArray(Charsets.UTF_8)) }
            info = "Patch project exported."
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            apkUri = uri
            apkName = DocumentFile.fromSingleUri(context, uri)?.name ?: "Selected APK"
            selected = null
            edits = emptyMap()
            loading = true
        }
    }

    LaunchedEffect(apkUri) {
        val uri = apkUri ?: return@LaunchedEffect
        entries = withContext(Dispatchers.IO) {
            val found = mutableListOf<String>()
            context.contentResolver.openInputStream(uri)?.use { input ->
                ZipInputStream(input).use { zip ->
                    var entry = zip.nextEntry
                    while (entry != null) {
                        if (!entry.isDirectory && !entry.name.startsWith("../") && "/../" !in entry.name) found += entry.name
                        entry = zip.nextEntry
                    }
                }
            }
            found.sorted()
        }
        loading = false
        info = "Loaded ${entries.size} archive entries. Select a text resource."
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Apkedite", style = MaterialTheme.typography.headlineMedium)
        Text("On-device APK resource workspace")
        Spacer(Modifier.height(12.dp))
        Button(onClick = { picker.launch(arrayOf("application/vnd.android.package-archive", "application/octet-stream")) }) {
            Text("Choose APK")
        }
        Text(apkName, style = MaterialTheme.typography.labelLarge)
        OutlinedTextField(value = query, onValueChange = { query = it }, label = { Text("Search files") }, modifier = Modifier.fillMaxWidth())
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        Text(info, Modifier.padding(vertical = 8.dp))
        Row(Modifier.weight(1f)) {
            LazyColumn(Modifier.weight(1f)) {
                items(entries.filter { it.contains(query, ignoreCase = true) }) { name ->
                    Text(name, Modifier.fillMaxWidth().clickable {
                        selected = name
                        val ext = name.substringAfterLast('.', "").lowercase()
                        if (ext in listOf("xml", "txt", "json", "html", "css", "js", "properties")) {
                            val uri = apkUri
                            if (uri != null) {
                                context.contentResolver.openInputStream(uri)?.use { raw ->
                                    ZipInputStream(raw).use { zip ->
                                        var entry = zip.nextEntry
                                        while (entry != null) {
                                            if (entry.name == name) {
                                                editorText = edits[name] ?: zip.readBytes().toString(Charsets.UTF_8)
                                                info = "Text resource: $name"
                                                break
                                            }
                                            entry = zip.nextEntry
                                        }
                                    }
                                }
                            }
                        } else {
                            editorText = ""
                            info = "Selected $name. Binary and image preview are scheduled for the next milestone."
                        }
                    }.padding(vertical = 8.dp))
                    HorizontalDivider()
                }
            }
            OutlinedTextField(
                value = editorText,
                onValueChange = { editorText = it },
                modifier = Modifier.weight(1.2f).fillMaxHeight(),
                label = { Text(selected ?: "Text resource") }
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                val name = selected
                if (name != null && name.substringAfterLast('.', "").lowercase() in
                    listOf("xml", "txt", "json", "html", "css", "js", "properties")) {
                    edits = edits + (name to editorText)
                    info = "Saved in workspace: ${edits.size} edited resource(s)"
                }
            }) { Text("Save edit") }
            OutlinedButton(onClick = { exportLauncher.launch("Apkedite-patch.json") }) {
                Text("Export patch")
            }
        }
        Text("Exported patch JSON can be used as a portable edit record. Rebuilding the APK is a desktop workflow in this milestone.",
            style = MaterialTheme.typography.bodySmall)
    }
}
