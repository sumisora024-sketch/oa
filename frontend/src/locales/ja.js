export default {
  app: { title: 'NIT OA system', logout: 'ログアウト', language: '言語', role: '権限', changePassword: 'パスワード変更' },
  nav: { home: 'ホーム', employees: '人員管理', internalEmployees: '内部人員管理', externalEmployees: '外部人員管理', contracts: '契約管理', internalContracts: '内部契約管理', externalContracts: '外部契約管理', externalContractsNew: '新規契約締結', externalPartners: '締結済み会社', documentManagement: '書類管理', purchaseOrders: '発注書作成', quotations: '見積書作成', invoices: '請求書作成', documentHistory: '書類履歴', documentLibrary: '全書類管理', approvals: '承認', contractApprovals: '契約承認', reimbursementApprovals: '経費承認', reimbursements: '経費精算', expenseSettlement: '経費・精算', reimbursementClaims: '経費申請', salaryDetails: '給与明細', monthlySettlement: '月次精算', subcontracting: '準委任', subcontractingNotice: '会社通知', subcontractingQuotations: '見積書', subcontractingInvoices: '請求書', subcontractingPersonnel: '入場者', attendance: '勤怠管理', attendanceSummary: '勤怠一覧', attendanceRequests: '勤怠申請', attendanceApprovals: '勤怠承認', attendanceSettings: 'カレンダー設定', projects: '案件管理', settings: 'システム設定', mailSettings: 'メール設定', permissionManagement: '権限管理' },
  login: { title: 'ログイン', email: 'メール', password: 'パスワード', submit: 'ログイン', forgot: 'パスワード再設定', sso: 'Teams SSO', eyebrow: 'NIT DX Portal', headline: '仕事をもっと楽に。', headlineAccent: 'NIT OA system', subhead: '人員・契約・案件をひとつにつなぎ、探す時間と確認の手間を減らします。', panelEyebrow: 'Staff entrance', panelHint: '必要な情報へ、迷わずすぐにアクセスできます。', capabilities: { people: '人員情報を見える化', contracts: '契約・給与をすぐ確認', projects: '案件アサインをスムーズに' }, forceResetTitle: '初回ログインのパスワード変更', forceResetHint: '初期パスワードを使用中です。先に新しいパスワードを設定してください。', changePasswordTitle: 'パスワード変更', changePasswordHint: '現在のパスワードを入力し、新しいパスワードを設定してください。', currentPassword: '現在のパスワード', newPassword: '新しいパスワード', confirmPassword: '新しいパスワード確認' },
  common: { search: '検索', create: '新規', edit: '編集', delete: '削除', save: '保存', cancel: 'キャンセル', import: '取込', upload: 'アップロード', download: 'ダウンロード', actions: '操作', refresh: '更新', analyze: '分析', recommend: '推薦', assign: 'アサイン', send: '送信', required: '必須', success: '成功', failed: '失敗', columns: '表示列', detail: '詳細', yes: 'はい', no: 'いいえ', confirmDelete: 'このレコードを削除しますか？' },
  validation: { required: '必須項目です', email: '有効なメールを入力してください', employeeName: '氏名は日本語・漢字・英字のみ入力できます', jpPhone: '日本国内の電話番号形式で入力してください', passwordMismatch: '新しいパスワードが一致しません' },
  fields: {
    id: 'ID', fullName: '氏名', nameKana: 'フリガナ', email: 'メール', platformEmail: 'ログインアカウント', phone: '電話', birthDate: '生年月日', age: '年齢', graduationStatus: '卒業状況', residence: '居住地', nearestStation: '最寄駅', nationality: '国籍', employeeType: '社員タイプ', languages: '語学力', certifications: '資格', technicalExperience: '技術経歴', itYears: 'IT経験年数', talentCategory: '人材分類', skills: 'スキル',
    title: 'タイトル', employee: '社員', contractType: '契約種別', vendorCompany: '契約会社', startDate: '開始日', endDate: '終了日',
    baseSalary: '基本給', allowanceTotal: '手当合計', baseUnitPriceLow: '基本単価（低）', baseUnitPriceHigh: '基本単価（高）', salaryTotalMonthly: '月額合計', duty: '業務内容',
    allowances: '手当明細', amount: '金額', pdfFile: 'PDF ファイル', parsedText: '解析テキスト', yearMonth: '年月', hoursRange: '基準時間帯', monthlyHours: '月間工数', estimatedSalary: '計算支給額', payableSalary: '支給予定額', actualSalary: '当月支給給与', reimbursementAmount: '経費精算', grossPaymentTotal: '総支給額', deductionTotal: '控除合計', taxablePaymentTotal: '課税支給額', socialInsuranceTotal: '社会保険合計', estimatedAnnualSalary: '想定年収', locked: 'ロック', pension: '年金', residentTax: '住民税', insuranceFee: '保険料', note: '備考',
    clientCompany: 'クライアント会社', projectName: '案件名', description: '案件概要', requiredSkills: '必要スキル', workplace: '勤務地', nationalityRequirement: '国籍条件', duration: '期間', headcount: '人数', assignedEmployees: 'アサイン社員', unitPrice: '単価', createdAt: '作成日時', subject: 'メール件名', body: 'メール本文', attachmentText: '添付テキスト',
    source: 'ソース', confidence: '信頼度', remoteType: 'リモート区分', station: '駅', aiError: 'AI エラー', rawEmail: '元メール', attributes: '解析属性'
  },
  home: { profile: '個人情報', contracts: '契約情報', salary: '給与', projects: '参画案件', noData: 'データなし', contactAdmin: 'メタデータ不足です。管理者に連絡してください', welcome: 'ようこそ、', heroCopy: '契約・給与・案件の状態を一つのポータルで確認できます。', partnerHero: 'パートナー向け準委任ポータルです。書類提出、入場者情報、固定資料を一箇所で管理できます。', salaryDetail: '給与明細', salarySummary: '給与サマリー', paymentItems: '支給', deductionItems: '控除', salaryCalculationNote: '給与額は勤怠・案件アサイン・承認済み経費・控除設定から自動計算されます。ロック済み月は自動再計算されません。', downloadPayslip: '給与明細PDF', downloadAnnual: '想定年収PDF', assistantGreeting: '会社情報や手続きについて質問できます。', assistantOnline: 'オンライン', assistantOffline: '未設定', assistantOfflineHint: 'AIアシスタントが未設定です。管理者に Dify の API Base と API Key を設定してもらってください。', assistantError: 'AIアシスタントでエラーが発生しました。', assistantPlaceholder: '質問を入力', assistantNewChat: '新しい会話', assistantSources: '参照', assistantSuggestionPeople: '入社・退職手続きについて教えて', assistantSuggestionExpense: '経費申請の流れを教えて', assistantSuggestionContract: '契約書類の提出方法を教えて' },
  employees: { importHelp: '通常表と技術者経歴書フォーマットに対応', employmentInfo: '在職情報', defaultPassword: "新規社員アカウントは 姓pinyin_名pinyin{'@'}nit-g.co.jp で生成され、初期パスワードは DEFAULT_EMPLOYEE_PASSWORD、初回ログイン時に変更必須です", resetPassword: 'パスワード初期化', resetPasswordConfirm: '{name} のパスワードを初期パスワードに戻しますか？', passwordResetDone: 'パスワードを初期化しました: {email}' },
  contracts: { importPdf: 'PDF契約を取込', due: '30日以内に終了', sendReminders: '期限通知を送信', longTerm: '長期', batchNote: '期限通知は毎日 09:00 の batch で自動送信され、宛先は HR_REMINDER_EMAIL です。', detailTitle: '契約詳細', salaryDetail: '給与・単価', contractInfo: '契約情報', salaryManagement: '給与明細' },
  external: {
    partners: '締結済み会社', contracts: '新規契約締結', documents: '書類作成', approvals: '承認', settlement: '月次精算',
    newPartner: '会社追加', newContract: '新規契約', uploadUpstream: '上位契約アップロード', companyName: '会社名', companyKana: '会社カナ', partnerType: '区分', partnerAccount: 'パートナーアカウント', temporaryPassword: '一時パスワード', sendPartnerAccount: 'アカウント情報を送信', sendPartnerAccountConfirm: '一時パスワードを再発行し、担当者メールへ送信しますか？', accountMailSent: 'アカウント情報を送信しました', accountMailMissingEmail: '担当者メールを入力してください',
    contractedAt: '締結日', contractedSuccess: '締結成功', contractEndDate: '契約終了日', terminated: '解約済み', contractActive: '契約有効', contactName: '担当者', relatedPeople: '関連担当者', address: '住所', direction: '上下流', status: '状態', fixedFiles: '固定ファイル', downloadFixedPack: '固定ファイル一括DL', useExistingCompany: '締結済み会社を選択',
    generateDocuments: '発注書 / 見積書 作成', generatePurchaseOrder: '発注書作成', generateQuotation: '見積書作成', invoiceFromQuotation: '見積書から請求書作成',
    selectQuotation: '見積書を選択', approvedQuotation: '承認済みパートナー見積書', approvedQuotationRequired: '承認済みパートナー見積書を選択してください', generateInvoice: '請求書作成', targetMonth: '対象年月', issueDate: '発行日', dueDate: '支払期限',
    itemName: '項目', quantity: '数量', unitPrice: '単価', baseHours: '基本時間幅', documentType: '書類種別', documentNo: '書類番号',
    total: '合計金額', invoiceTotal: '請求書合計', purchaseTotal: 'パートナー請求書合計', salaryTotal: '実支給給与合計', netIncome: '当月収支',
    downstreamOnly: '発注書は downstream または both の会社のみ作成できます',
    upstreamOnly: '見積書と請求書は upstream または both の会社のみ作成できます',
    documentRuleHint: '書類方向：downstream は発注書のみ、upstream は見積書と請求書、both はすべて作成できます。',
    invoiceDetails: '請求書入金明細', purchaseDetails: 'パートナー請求書支払明細', received: '入金済み', receivedAmount: '入金額', paid: '支払済み', paidAmount: '支払額', effectiveAmount: '計上額',
    pendingApprovals: '未処理承認', approvalStatus: '承認状態', approve: '承認', reject: '却下', withdraw: '承認取消',
    documentTypes: { purchase_order: '発注書', quotation: '見積書', invoice: '請求書', uploaded_contract: 'アップロード契約', partner_quotation: 'パートナー見積書', partner_invoice: 'パートナー請求書' }
  },
  subcontracting: { partnerQuotation: 'パートナー見積書', submitQuotation: '見積書をアップロード', quotationFile: '見積書ファイル', approvalStatus: '承認状態', entryPersonnel: '入場者', assignmentMonth: '委派月', submitPersonnel: '人員を提出', companyNotice: '会社通知/声明' },
  reimbursements: { expenseType: '経費種別', period: '対象月', periodStart: '開始月', periodEnd: '終了月', payMonth: '支給月', files: '領収書/証憑', traffic: '交通費', businessTrip: '出張費', teamBuilding: '懇親会費', other: 'その他' },
  approvals: { contractApprovals: '契約承認', reimbursementApprovals: '経費承認', attendanceApprovals: '勤怠承認' },
  permissions: { hint: 'この設定は前端メニューとルート表示のみを制御します。API 権限は既存のロール権限で保護されます。', role: '対象ロール' },
  projects: { analyzeEmail: 'メールから案件化', pollMailbox: 'メール取込', recommendations: '候補者推薦', reasons: '理由', score: 'スコア', detailTitle: '案件詳細', aiResult: 'AI 解析結果', assignmentFull: '必要人数に達したため、これ以上アサインできません', reassign: '再アサイン', unassign: 'アサイン解除', unassignConfirm: 'この人員の案件アサインを解除しますか？' }
  ,
  settings: {
    mail: 'メール設定', provider: '方式', disabled: '無効', gmail: 'Gmail App Password', generic: '汎用 IMAP+SMTP', smtpOnly: 'SMTP のみ',
    enabled: '有効', imapEnabled: '受信を有効化', smtpEnabled: '送信を有効化', imapHost: 'IMAP ホスト', imapPort: 'IMAP ポート', imapUsername: 'IMAP アカウント', imapPassword: 'IMAP パスワード', imapFolder: 'メールボックス',
    smtpHost: 'SMTP ホスト', smtpPort: 'SMTP ポート', smtpUsername: 'SMTP アカウント', smtpPassword: 'SMTP パスワード', smtpFrom: '送信元', smtpTls: 'STARTTLS', pollInterval: '監視間隔秒',
    hasPassword: '保存済みパスワード', testImap: '受信テスト', testSmtp: '送信テスト'
  }
}
