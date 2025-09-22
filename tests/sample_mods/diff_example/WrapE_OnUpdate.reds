// Wrap method by ModE to create coexistence bonus
@wrapMethod
public func FooClass::OnUpdate(delta: Float) -> Int32 {
  let orig = wrappedMethod(delta);
  return orig + 10;
}
