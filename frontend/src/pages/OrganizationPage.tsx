import { useState } from "react";
import { useNavigate } from "react-router";

import { errorText } from "../api/client";
import type { MemberRole, OrgMember, Organization } from "../api/monitoring";
import {
  useAddMember,
  useDeleteOrganization,
  useMembers,
  useRemoveMember,
  useRenameOrganization,
  useSetMemberRole,
} from "../api/queries";
import { useUser } from "../auth/AuthProvider";
import { Avatar } from "../components/Avatar";
import { AvatarDialog } from "../components/AvatarDialog";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Dialog } from "../components/Dialog";
import { HeadAvatar } from "../components/HeadAvatar";
import { SelectField } from "../components/SelectField";
import { TextField } from "../components/TextField";
import { useSave } from "../components/useSave";
import { formatDate } from "../format";
import { useOrg } from "../org/OrgProvider";
import "./Page.css";

const ROLE_LABEL: Record<MemberRole, string> = { owner: "Owner", admin: "Admin", member: "Member" };
const RANK: Record<MemberRole, number> = { member: 0, admin: 1, owner: 2 };

type Modal =
  | { kind: "rename" }
  | { kind: "avatar" }
  | { kind: "add" }
  | { kind: "remove"; member: OrgMember }
  | { kind: "leave" }
  | { kind: "delete" }
  | null;

/** The current organization: its members and settings. What you can change depends on your role. */
export function OrganizationPage() {
  const { current, isLoading } = useOrg();
  if (isLoading) return <p className="page page__note">Loading…</p>;
  if (!current) return <p className="page page__note">You don't belong to any organization.</p>;
  // Remount per org so dialogs and mutations never point at the previous one.
  return <OrganizationSettings key={current.id} org={current} />;
}

function OrganizationSettings({ org }: { org: Organization }) {
  const user = useUser();
  const { orgs, select } = useOrg();
  const navigate = useNavigate();
  const members = useMembers(org.id);
  const setRole = useSetMemberRole(org.id);
  const [modal, setModal] = useState<Modal>(null);
  const close = () => setModal(null);

  const me = members.data?.find((m) => m.user_id === user.id);
  const myRank = me ? RANK[me.role] : -1;
  const isShared = org.org_type === "team";
  const ownerCount = members.data?.filter((m) => m.role === "owner").length ?? 0;
  // After leaving or deleting, fall back to the personal org.
  const goHome = () => {
    const personal = orgs.find((o) => o.org_type === "personal" && o.id !== org.id);
    if (personal) select(personal.id);
    navigate("/");
  };

  return (
    <div className="page">
      <div className="page__head">
        <HeadAvatar
          name={org.name}
          avatar={org}
          editable={myRank >= RANK.admin}
          onEdit={() => setModal({ kind: "avatar" })}
        />
        <div className="page__heading">
          <h1 className="page__title">{org.name}</h1>
          <p className="page__subtitle">
            <Chip tone={isShared ? "info" : "neutral"}>{isShared ? "Shared" : "Personal"}</Chip>{" "}
            <Chip>{org.plan[0].toUpperCase() + org.plan.slice(1)} plan</Chip>
            {me && <> · You are {ROLE_LABEL[me.role].toLowerCase()}</>}
          </p>
        </div>
        <div className="page__actions">
          {myRank >= RANK.admin && (
            <Button variant="text" onClick={() => setModal({ kind: "rename" })}>
              Rename
            </Button>
          )}
        </div>
      </div>

      {!isShared && (
        <div className="blank">
          <h2 className="blank__title">This is your personal organization</h2>
          <p>Only you can see it. To track competitors with colleagues, create a shared organization from the organization menu.</p>
        </div>
      )}

      {isShared && (
        <section className="page__section" aria-labelledby="members-title">
          <div className="page__section-head">
            <h2 id="members-title" className="page__section-title">
              Members{members.data ? ` (${members.data.length})` : ""}
            </h2>
            {myRank >= RANK.admin && <Button onClick={() => setModal({ kind: "add" })}>Add member</Button>}
          </div>
          {members.isLoading && <p className="page__note">Loading members…</p>}
          {members.error && <p className="page__error">{errorText(members.error)}</p>}
          {members.data && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Member</th>
                    <th scope="col">Role</th>
                    <th scope="col">Joined</th>
                    <th scope="col">
                      <span className="visually-hidden">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {members.data.map((m) => {
                    const isMe = m.user_id === user.id;
                    const lastOwner = m.role === "owner" && ownerCount === 1;
                    return (
                      <tr key={m.id}>
                        <td>
                          <div className="member member--with-avatar">
                            <Avatar name={m.full_name || m.email} avatar={m} size={36} round />
                            <span className="member__name">
                              {m.full_name || m.email}
                              {isMe && <span className="page__note"> (you)</span>}
                            </span>
                            {m.full_name && <span className="member__email">{m.email}</span>}
                          </div>
                        </td>
                        <td>
                          {myRank === RANK.owner ? (
                            <select
                              className="role-select"
                              value={m.role}
                              aria-label={`Role of ${m.email}`}
                              disabled={setRole.isPending || lastOwner}
                              title={lastOwner ? "An organization needs at least one owner" : undefined}
                              onChange={(e) => setRole.mutate({ userId: m.user_id, role: e.target.value as MemberRole })}
                            >
                              {(Object.keys(ROLE_LABEL) as MemberRole[]).map((r) => (
                                <option key={r} value={r}>
                                  {ROLE_LABEL[r]}
                                </option>
                              ))}
                            </select>
                          ) : (
                            ROLE_LABEL[m.role]
                          )}
                        </td>
                        <td>{formatDate(m.joined_at)}</td>
                        <td>
                          <div className="table__actions">
                            {isMe ? (
                              <Button
                                variant="text"
                                className="btn--danger"
                                disabled={lastOwner}
                                title={lastOwner ? "Make someone else an owner before leaving" : undefined}
                                onClick={() => setModal({ kind: "leave" })}
                              >
                                Leave
                              </Button>
                            ) : (
                              myRank === RANK.owner && (
                                <Button
                                  variant="text"
                                  className="btn--danger"
                                  onClick={() => setModal({ kind: "remove", member: m })}
                                >
                                  Remove
                                </Button>
                              )
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {setRole.error && <p className="page__error">{errorText(setRole.error)}</p>}
          <p className="page__note org-roles">
            <b>Members</b> track competitors and generate reports. <b>Admins</b> also add members, rename the organization and
            manage workspaces. <b>Owners</b> also change roles, remove members and delete the organization.
          </p>
        </section>
      )}

      {isShared && myRank === RANK.owner && (
        <section className="page__section danger-zone" aria-labelledby="danger-title">
          <h2 id="danger-title" className="page__section-title">
            Delete organization
          </h2>
          <p className="page__note">
            Deletes the organization with all of its workspaces, competitors, scrape history and reports.
          </p>
          <Button variant="text" className="btn--danger" onClick={() => setModal({ kind: "delete" })}>
            Delete {org.name}
          </Button>
        </section>
      )}

      {modal?.kind === "rename" && <RenameDialog org={org} onClose={close} />}
      {modal?.kind === "avatar" && (
        <AvatarDialog kind="organization" id={org.id} name={org.name} avatar={org} onClose={close} />
      )}
      {modal?.kind === "add" && <AddMemberDialog orgId={org.id} canGrantOwner={myRank === RANK.owner} onClose={close} />}
      {modal?.kind === "remove" && (
        <RemoveMember orgId={org.id} userId={user.id} member={modal.member} onClose={close} onDone={close} />
      )}
      {modal?.kind === "leave" && me && (
        <RemoveMember orgId={org.id} userId={user.id} member={me} onClose={close} onDone={goHome} />
      )}
      {modal?.kind === "delete" && <DeleteOrganization org={org} onClose={close} onDeleted={goHome} />}
    </div>
  );
}

function RenameDialog({ org, onClose }: { org: Organization; onClose: () => void }) {
  const rename = useRenameOrganization(org.id);
  const [name, setName] = useState(org.name);
  const save = useSave(async (value: string) => {
    await rename.mutateAsync(value);
    onClose();
  });
  return (
    <Dialog
      open
      title="Rename organization"
      onClose={onClose}
      onSubmit={() => (name.trim() ? save.run(name.trim()) : save.setError("Enter a name"))}
      busy={save.busy}
      error={save.error}
    >
      <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} autoFocus maxLength={255} />
    </Dialog>
  );
}

function AddMemberDialog({
  orgId,
  canGrantOwner,
  onClose,
}: {
  orgId: string;
  canGrantOwner: boolean;
  onClose: () => void;
}) {
  const add = useAddMember(orgId);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MemberRole>("member");
  const [emailError, setEmailError] = useState<string | null>(null);
  const save = useSave(async () => {
    await add.mutateAsync({ email: email.trim(), role });
    onClose();
  });
  const roles = (canGrantOwner ? ["member", "admin", "owner"] : ["member", "admin"]) as MemberRole[];

  const submit = () => {
    const problem = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) ? null : "Enter an email address";
    setEmailError(problem);
    if (!problem) save.run();
  };

  return (
    <Dialog
      open
      title="Add member"
      confirmLabel="Add"
      onClose={onClose}
      onSubmit={submit}
      busy={save.busy}
      error={save.error}
    >
      <p className="dialog__lead">They need a Kuzot account first. They'll see this organization in their organization menu.</p>
      <TextField
        label="Email"
        type="email"
        autoComplete="off"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        error={emailError}
        autoFocus
      />
      <SelectField
        label="Role"
        value={role}
        onChange={(e) => setRole(e.target.value as MemberRole)}
        options={roles.map((r) => ({ value: r, label: ROLE_LABEL[r] }))}
      />
    </Dialog>
  );
}

function RemoveMember({
  orgId,
  userId,
  member,
  onClose,
  onDone,
}: {
  orgId: string;
  userId: string;
  member: OrgMember;
  onClose: () => void;
  onDone: () => void;
}) {
  const remove = useRemoveMember(orgId, userId);
  const leaving = member.user_id === userId;
  return (
    <ConfirmDialog
      title={leaving ? "Leave this organization?" : "Remove member?"}
      confirmLabel={leaving ? "Leave" : "Remove"}
      onConfirm={async () => {
        await remove.mutateAsync(member.user_id);
        onDone();
      }}
      onClose={onClose}
    >
      {leaving
        ? "You'll lose access to its workspaces and reports. An owner can add you back."
        : `${member.full_name || member.email} will lose access to this organization's workspaces and reports.`}
    </ConfirmDialog>
  );
}

function DeleteOrganization({ org, onClose, onDeleted }: { org: Organization; onClose: () => void; onDeleted: () => void }) {
  const remove = useDeleteOrganization(org.id);
  return (
    <ConfirmDialog
      title={`Delete ${org.name}?`}
      confirmLabel="Delete organization"
      onConfirm={async () => {
        await remove.mutateAsync();
        onDeleted();
      }}
      onClose={onClose}
    >
      All of its workspaces, competitors, scrape history and reports will be deleted for every member. This can't be
      undone.
    </ConfirmDialog>
  );
}
