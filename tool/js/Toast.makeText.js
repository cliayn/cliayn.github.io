Java.perform(function () {
    console.log("[*] 脚本修复版已加载，正在深度监控弹窗与 Dialog...");

    // --- 1. 监控 Toast (改为 Hook 静态方法 makeText) ---
    var Toast = Java.use("android.widget.Toast");
    // 拦截 makeText(Context, CharSequence, int)
    Toast.makeText.overload('android.content.Context', 'java.lang.CharSequence', 'int').implementation = function (context, text, duration) {
        console.log("\n[!] 触发 Toast.makeText()，内容为: " + text);
        printStack();
        return this.makeText(context, text, duration);
    };

    // --- 2. 监控 AlertDialog.Builder (设置消息) ---
    var AlertDialogBuilder = Java.use("android.app.AlertDialog$Builder");
    
    // 拦截 setMessage
    AlertDialogBuilder.setMessage.overload('java.lang.CharSequence').implementation = function (msg) {
        console.log("\n[!] 触发 AlertDialog.setMessage()，内容为: " + msg);
        printStack();
        return this.setMessage(msg);
    };

    // 拦截 setTitle (有些检测结果写在标题里)
    AlertDialogBuilder.setTitle.overload('java.lang.CharSequence').implementation = function (title) {
        console.log("\n[!] 触发 AlertDialog.setTitle()，标题为: " + title);
        return this.setTitle(title);
    };

    // --- 3. 监控通用的 Dialog 显示 (最后的防线) ---
    var Dialog = Java.use("android.app.Dialog");
    Dialog.show.implementation = function () {
        console.log("\n[!] 发现 Dialog.show() 被调用 (通常是确认框)");
        printStack();
        this.show();
    };

    // --- 4. 核心辅助函数：精准定位调用栈 ---
    function printStack() {
        var Thread = Java.use("java.lang.Thread");
        var stack = Thread.currentThread().getStackTrace();
        console.log("-------------------- 调用栈轨迹 --------------------");
        for (var i = 0; i < stack.length; i++) {
            var frame = stack[i].toString();
            // 重点标记业务代码
            if (frame.indexOf("ksbd") !== -1 || frame.indexOf("kaoshibaodian") !== -1) {
                console.log("  >>> [关键代码]: " + frame);
            } else {
                // 打印出前几层系统调用辅助判断
                if (i < 15) console.log("      " + frame);
            }
        }
        console.log("----------------------------------------------------");
    }
});